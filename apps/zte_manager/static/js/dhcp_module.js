/* Device-driven DHCP management. No application/operator access tiers. */
(() => {
  "use strict";
  const id = name => document.getElementById(name);
  let snapshot = null, busy = false, pageEpoch = 0;
  const tableCell = (row, value) => {
    const node = document.createElement("td");
    node.textContent = value === undefined || value === null || value === ""
      ? "—" : String(value);
    row.append(node);
  };
  const feedback = (message, level = "") => {
    if (!id("dhcpFeedback")) return;
    id("dhcpFeedback").textContent = message;
    id("dhcpFeedback").dataset.level = level;
  };
  function fill(data) {
    snapshot = data;
    const basic = data.basic || {};
    const capabilities = data.capabilities || {};
    id("dhcpEnabled").checked = String(basic.ServerEnable) === "1";
    for (const [key, field] of Object.entries({
      dhcpStart:"MinAddress", dhcpEnd:"MaxAddress",
      dhcpLease:"LeaseTime", dhcpDns1:"DNSServer1", dhcpDns2:"DNSServer2"
    })) id(key).value = basic[field] ?? "";
    let gateway = id("dhcpGateway");
    if (capabilities.gateway_write && !gateway) {
      const label = document.createElement("label");
      label.className = "field";
      label.innerHTML = '<span>Gateway DHCP</span>';
      gateway = document.createElement("input");
      gateway.id = "dhcpGateway";
      gateway.inputMode = "decimal";
      label.append(gateway);
      id("dhcpStart").closest(".field-grid").append(label);
    }
    if (gateway) {
      gateway.closest(".field").hidden = !capabilities.gateway_write;
      gateway.value = basic.IPRouters || basic.IPAddr || "";
    }
    const canEdit = Boolean(
      capabilities.server_write === undefined ? basic._InstID :
      capabilities.server_write
    );
    for (const element of id("dhcpConfigForm").querySelectorAll("input"))
      element.disabled = !canEdit;
    id("dhcpApply").disabled = !canEdit;
    id("dhcpAvailability").textContent = canEdit
      ? "Parâmetros obtidos da sessão autenticada da ONT."
      : "Esta sessão/firmware não disponibilizou o formulário de gravação DHCP.";
    const leases = id("dhcpLeases");
    leases.replaceChildren();
    for (const item of data.leases || []) {
      const tr = document.createElement("tr");
      tableCell(tr, item.HostName || item.hostname);
      tableCell(tr, item.IPAddr || item.IPAddress);
      tableCell(tr, item.MACAddr || item.MACAddress);
      tableCell(tr, item.RemainingLeaseTime || item.LeaseTime);
      leases.append(tr);
    }
    if (!leases.children.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = capabilities.lease_read === false
        ? "A ONT não disponibilizou a tabela de concessões."
        : "Nenhuma concessão retornada; leases não representam conexão ativa.";
      row.append(cell); leases.append(row);
    }
    renderIpv6(data);
    renderReservations(data);
    const notes = data.warnings || [];
    if (notes.length) feedback(notes.join(" · "));
  }
  async function refresh() {
    if (!ontConnected) return;
    const epoch = pageEpoch;
    feedback("Lendo parâmetros DHCP e concessões…");
    try {
      const data = await apiRequest("/network/dhcp");
      if (epoch !== pageEpoch) return;
      fill(data);
    } catch(error) {
      feedback("O firmware não confirmou os dados DHCP: " + error.message, "error");
    }
  }
  async function apply(event) {
    event.preventDefault();
    if (busy || !snapshot) return;
    const old = snapshot.basic || {};
    const changes = {};
    const values = {
      enabled: id("dhcpEnabled").checked,
      min_address: id("dhcpStart").value.trim(),
      max_address: id("dhcpEnd").value.trim(),
      dns1: id("dhcpDns1").value.trim(),
      dns2: id("dhcpDns2").value.trim(),
      lease_time: Number(id("dhcpLease").value)
    };
    const names = {
      enabled:"ServerEnable", min_address:"MinAddress",
      max_address:"MaxAddress", dns1:"DNSServer1",
      dns2:"DNSServer2", lease_time:"LeaseTime"
    };
    for (const [key, field] of Object.entries(names)) {
      const current = field === "ServerEnable"
        ? String(old[field]) === "1" : String(old[field] ?? "");
      if (String(values[key]) !== String(current)) changes[key] = values[key];
    }
    if (id("dhcpGateway") && !id("dhcpGateway").closest(".field").hidden &&
        id("dhcpGateway").value.trim() !== (old.IPRouters || old.IPAddr || ""))
      changes.gateway = id("dhcpGateway").value.trim();
    if (!Object.keys(changes).length) {
      feedback("A configuração já possui os valores selecionados.", "ok");
      return;
    }
    busy = true; id("dhcpApply").disabled = true;
    feedback("Aplicando DHCP na ONT. Alterações podem interromper clientes…");
    setBusy(true, "Atualizando DHCP e verificando persistência…");
    try {
      const report = await apiRequest("/network/dhcp/update", {
        method:"POST", body:JSON.stringify(changes)
      });
      feedback(report.success && report.verified !== false
        ? "DHCP aplicado e verificado por nova leitura."
        : "A ONT não confirmou a alteração. Confira o equipamento.",
        report.success && report.verified !== false ? "ok" : "error");
      if (report.success) await refresh();
    } catch (error) {
      feedback("Aplicação não confirmada: " + error.message +
        ". Verifique a ONT antes de tentar novamente.", "error");
    } finally {
      busy = false; id("dhcpApply").disabled = false;
      setBusy(false);
    }
  }
