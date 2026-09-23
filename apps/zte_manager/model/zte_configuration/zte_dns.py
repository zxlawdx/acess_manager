import ipaddress
import time
import xml.etree.ElementTree as ET

from .zte_post import post_menu


# =========================================================
# DNS
# =========================================================


def dns_status_raw(zte):
    """
    Lê o bloco principal de DNS.

    A view "dns" reúne três formulários no firmware ThinkLua:
        - nome do domínio;
        - nomes de servidor / hosts estáticos;
        - servidores DNS IPv4/IPv6.

    O domínio e os servidores usam dns_localdns_lua.lua.
    """

    zte.get_view(
        "dns",
        Menu3Location=0
    )

    return zte.get_menu(
        "dns_localdns_lua.lua"
    )


def dns_hosts_raw(zte):
    """
    Lê a seção "Nome de servidor".

    dns_hostname_lua.lua devolve ALLDNSHOST. O objeto pode misturar hosts
    manuais e nomes aprendidos pelo DHCP, então a leitura abaixo filtra os
    registros DHCP antes de transformá-los em configuração do atendente.
    """

    zte.get_view(
        "dns",
        Menu3Location=0
    )

    return zte.get_menu(
        "dns_hostname_lua.lua"
    )


def dns_status(zte):
    xml = dns_status_raw(
        zte
    )

    zte._validar_resposta(
        xml
    )

    dados = zte._parse_instances(
        xml
    )

    instancias = dados.get(
        "OBJ_DNS_ID",
        []
    )

    dns = (
        instancias[0]
        if instancias
        else {}
    )

    hosts_xml = dns_hosts_raw(
        zte
    )

    zte._validar_resposta(
        hosts_xml
    )

    return {
        "id": dns.get("_InstID"),
        "domain_name": dns.get("DomainName"),
        "ipv4_1": dns.get("SerIPAddress1"),
        "ipv4_2": dns.get("SerIPAddress2"),
        "ipv6_1": dns.get("SerIPv6Address1"),
        "ipv6_2": dns.get("SerIPv6Address2"),
        "hosts": _parse_hosts(
            hosts_xml
        ),
    }


def set_dns(
    zte,
    config
):
    """
    Aplica o bloco DNS da configuração padrão.

    A página original parece uma tela única, mas o JavaScript do ZTE envia
    três POSTs diferentes. Mantemos o mesmo fluxo para não inventar payload:

        menuView dns
            -> LocalDns / DomainName
            -> LocalDnsServer / DNS IPv4 + IPv6
            -> HostName / nomes estáticos

    As entradas de "Nome de servidor" são tratadas como upsert. O perfil cria
    ou atualiza os nomes que conhece, mas não apaga entradas extras da ONT.
    Isso evita remover configuração que pertença a outro serviço.
    """

    atual = dns_status(
        zte
    )

    novo = {
        "domain_name": config.get(
            "domain_name",
            atual.get("domain_name") or ""
        ),
        "ipv4_1": config.get(
            "ipv4_1",
            atual.get("ipv4_1") or ""
        ),
        "ipv4_2": config.get(
            "ipv4_2",
            atual.get("ipv4_2") or ""
        ),
        "ipv6_1": config.get(
            "ipv6_1",
            atual.get("ipv6_1") or "::"
        ) or "::",
        "ipv6_2": config.get(
            "ipv6_2",
            atual.get("ipv6_2") or "::"
        ) or "::",
    }

    _validate_dns(
        novo
    )

    _apply_domain_name(
        zte,
        atual.get("id") or "IGD",
        novo["domain_name"]
    )

    _apply_dns_servers(
        zte,
        atual.get("id") or "IGD",
        novo
    )

    resultados_hosts = []

    for host in config.get(
        "hosts",
        []
    ):
        resultado_host = _upsert_host(
            zte,
            host
        )

        resultados_hosts.append(
            resultado_host
        )

        # O backend responde SUCC antes de a nova instância aparecer em
        # ALLDNSHOST em alguns builds. Esperamos a confirmação da gravação
        # antes de criar o próximo host para não perder a segunda entrada.
        _wait_host_applied(
            zte,
            resultado_host["nome"],
            resultado_host["ip"]
        )

    return {
        "success": True,
        **novo,
        "hosts": resultados_hosts,
    }


def _apply_domain_name(
    zte,
    inst_id,
    domain_name
):
    """
    Reproduz o formulário dns_localdns_t.lp.

    O token temporário pertence à menuView atual. Por isso abrimos a view
    imediatamente antes do POST; post_menu() acrescenta _sessionTOKEN por
    último e calcula o Check sobre o body final quando o firmware exige.
    """

    zte.get_view(
        "dns",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "dns_localdns_lua.lua",
        [
            ("IF_ACTION", "Apply"),
            ("_InstID", inst_id),
            ("DomainName", domain_name),
            ("Btn_cancel_instCfgArea", ""),
            ("Btn_apply_instCfgArea", ""),
        ]
    )

    zte._validar_resposta(
        resposta
    )


def _apply_dns_servers(
    zte,
    inst_id,
    config
):
    """
    Reproduz o formulário dns_dnsserver_t.lp.

    O JavaScript original converte IPv6 vazio para "::" antes de serializar.
    """

    zte.get_view(
        "dns",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "dns_localdns_lua.lua",
        [
            ("IF_ACTION", "Apply"),
            ("_InstID", inst_id),
            ("SerIPAddress1", config["ipv4_1"]),
            ("SerIPAddress2", config["ipv4_2"]),
            ("SerIPv6Address1", config["ipv6_1"]),
            ("SerIPv6Address2", config["ipv6_2"]),
            ("Btn_cancel_LocalDnsServer", ""),
            ("Btn_apply_LocalDnsServer", ""),
        ]
    )

    zte._validar_resposta(
        resposta
    )

    # Alguns builds confirmam SUCC antes de persistir o segundo servidor.
    # Fazemos read-after-write e um único retry para evitar falso positivo.
    if not _wait_dns_servers_applied(
        zte,
        config
    ):
        zte.get_view(
            "dns",
            Menu3Location=0
        )

        resposta = post_menu(
            zte,
            "dns_localdns_lua.lua",
            [
                ("IF_ACTION", "Apply"),
                ("_InstID", inst_id),
                ("SerIPAddress1", config["ipv4_1"]),
                ("SerIPAddress2", config["ipv4_2"]),
                ("SerIPv6Address1", config["ipv6_1"]),
                ("SerIPv6Address2", config["ipv6_2"]),
                ("Btn_cancel_LocalDnsServer", ""),
                ("Btn_apply_LocalDnsServer", ""),
            ]
        )

        zte._validar_resposta(
            resposta
        )

        if not _wait_dns_servers_applied(
            zte,
            config
        ):
            raise RuntimeError(
                "A ONT respondeu SUCC, mas não confirmou todos os servidores DNS."
            )


def _wait_dns_servers_applied(
    zte,
    config,
    tentativas=6,
    intervalo=0.35
):
    esperado = {
        "SerIPAddress1": config.get("ipv4_1") or "",
        "SerIPAddress2": config.get("ipv4_2") or "",
        "SerIPv6Address1": config.get("ipv6_1") or "::",
        "SerIPv6Address2": config.get("ipv6_2") or "::",
    }

    for tentativa in range(tentativas):
        xml = dns_status_raw(
            zte
        )

        zte._validar_resposta(
            xml
        )

        instancias = (
            zte._parse_instances(xml)
            .get(
                "OBJ_DNS_ID",
                []
            )
        )

        atual = (
            instancias[0]
            if instancias
            else {}
        )

        if all(
            (atual.get(campo) or "") == valor
            for campo, valor in esperado.items()
        ):
            return True

        if tentativa < tentativas - 1:
            time.sleep(
                intervalo
            )

    return False


# =========================================================
# HOSTS DNS
# =========================================================




def _wait_host_applied(
    zte,
    nome,
    ip,
    tentativas=6,
    intervalo=0.35
):
    """
    Confirma a persistência do host antes de liberar o próximo POST.

    O P6N34 já devolveu HTTP 200/SUCC para duas criações consecutivas, mas a
    segunda entrada não apareceu na interface. O firmware grava instâncias
    assíncronas; serializar criação + confirmação evita essa corrida.
    """

    for tentativa in range(tentativas):
        xml = dns_hosts_raw(
            zte
        )

        zte._validar_resposta(
            xml
        )

        hosts = _parse_hosts(
            xml
        )

        encontrado = next((
            host
            for host in hosts
            if host.get("nome") == nome
            and host.get("ip") == ip
        ), None)

        if encontrado:
            return encontrado

        if tentativa < tentativas - 1:
            time.sleep(
                intervalo
            )

    # Um único retry é suficiente para a condição observada. Repetir
    # indefinidamente poderia criar duplicatas em firmwares que demoram mais
    # para atualizar a lista.
    _upsert_host_once(
        zte,
        nome,
        ip
    )

    for tentativa in range(tentativas):
        xml = dns_hosts_raw(
            zte
        )

        zte._validar_resposta(
            xml
        )

        hosts = _parse_hosts(
            xml
        )

        encontrado = next((
            host
            for host in hosts
            if host.get("nome") == nome
            and host.get("ip") == ip
        ), None)

        if encontrado:
            return encontrado

        if tentativa < tentativas - 1:
            time.sleep(
                intervalo
            )

    raise RuntimeError(
        f"A ONT respondeu SUCC, mas não confirmou a entrada DNS {nome} -> {ip}."
    )


def _upsert_host_once(
    zte,
    nome,
    ip
):
    xml = dns_hosts_raw(
        zte
    )

    zte._validar_resposta(
        xml
    )

    atuais = _parse_hosts(
        xml
    )

    existente = next((
        item
        for item in atuais
        if item.get("nome") == nome
    ), None)

    inst_id = (
        existente.get("id")
        if existente
        else "-1"
    )

    zte.get_view(
        "dns",
        Menu3Location=0
    )

    resposta = post_menu(
        zte,
        "dns_hostname_lua.lua",
        [
            ("IF_ACTION", "Apply"),
            ("_InstID", inst_id),
            ("OBJID", "DNS"),
            ("LeaseTime", "isDNSHOSTInst"),
            ("HostName", nome),
            ("IPAddress", ip),
        ]
    )

    zte._validar_resposta(
        resposta
    )

    return {
        "nome": nome,
        "ip": ip,
        "success": True,
    }

def _upsert_host(
    zte,
    host
):
    nome = str(
        host.get("nome", "")
    ).strip()

    ip = str(
        host.get("ip", "")
    ).strip()

    _validate_host(
        nome,
        ip
    )

    return _upsert_host_once(
        zte,
        nome,
        ip
    )


def _parse_hosts(xml_text):
    try:
        root = ET.fromstring(
            xml_text
        )
    except ET.ParseError:
        return []

    container = root.find(
        "ALLDNSHOST"
    )

    if container is None:
        return []

    resultado = []

    for instance in container.findall(
        "Instance"
    ):
        dados = {}
        filhos = list(
            instance
        )

        indice = 0

        while indice < len(filhos) - 1:
            if (
                filhos[indice].tag == "ParaName"
                and filhos[indice + 1].tag == "ParaValue"
            ):
                dados[
                    filhos[indice].text or ""
                ] = filhos[indice + 1].text or ""

                indice += 2
            else:
                indice += 1

        # O backend concatena hosts DHCP e hosts manuais em ALLDNSHOST.
        # Os registros DHCP possuem LeaseTime real; os manuais não retornam
        # LeaseTime (ou podem vir marcados como isDNSHOSTInst em variantes).
        if dados.get("LeaseTime") not in (
            None,
            "",
            "isDNSHOSTInst",
        ):
            continue

        if not dados.get("HostName"):
            continue

        resultado.append({
            "id": dados.get("_InstID"),
            "nome": dados.get("HostName"),
            "ip": dados.get("IPAddress"),
            "lease_time": dados.get("LeaseTime"),
        })

    return resultado


# =========================================================
# VALIDATION
# =========================================================


def _validate_dns(config):
    for campo in (
        "ipv4_1",
        "ipv4_2",
    ):
        valor = config.get(
            campo
        )

        if not valor:
            continue

        try:
            ipaddress.IPv4Address(
                valor
            )
        except ipaddress.AddressValueError as erro:
            raise ValueError(
                f"{campo} não é um IPv4 válido: {valor}"
            ) from erro

    for campo in (
        "ipv6_1",
        "ipv6_2",
    ):
        valor = config.get(
            campo
        )

        if not valor or valor == "::":
            continue

        try:
            ipaddress.IPv6Address(
                valor
            )
        except ipaddress.AddressValueError as erro:
            raise ValueError(
                f"{campo} não é um IPv6 válido: {valor}"
            ) from erro


def _validate_host(
    nome,
    ip
):
    if not nome or not ip:
        raise ValueError(
            "Nome e IP são obrigatórios para uma entrada DNS."
        )

    if len(nome) > 255:
        raise ValueError(
            "O nome do servidor DNS deve ter no máximo 255 caracteres."
        )

    try:
        nome.encode(
            "ascii"
        )
    except UnicodeEncodeError as erro:
        raise ValueError(
            "O nome do servidor DNS deve usar caracteres ASCII."
        ) from erro

    try:
        ipaddress.ip_address(
            ip
        )
    except ValueError as erro:
        raise ValueError(
            f"IP inválido para {nome}: {ip}"
        ) from erro
