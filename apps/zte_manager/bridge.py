from vela.core.bridge import BaseBridge


class ZTEBridge(BaseBridge):
    """
    Bridge do desktop.

    O BaseBridge atual do Vela faz hot reload de todos os módulos `apps.*`
    em cada `navigate()`. Isso é útil em páginas stateless, mas nesta aplicação
    a sessão HTTP com a ONT fica guardada em um singleton de Service Layer.

    Recarregar `apps.zte_manager.services.zte_service` durante uma navegação
    recriaria esse singleton e perderia a sessão da ONT. Como esta aplicação é
    uma SPA dentro de uma única rota Vela, desabilitamos apenas esse hot reload
    automático. A ideia do framework continua intacta e o estado do equipamento
    passa a ter o ciclo de vida correto da janela desktop.
    """

    def _reload_app_modules(self):
        return
