# Changelog

## 0.4.1 — Correção do perfil no Vela

- Corrige erro `Cannot read properties of null (reading 'querySelector')` após login.
- `profileRadios` agora cria os cards 2.4 GHz e 5 GHz antes de preencher o formulário.
- Adicionadas validações explícitas do DOM para evitar falhas silenciosas no WebView.
- Login bem-sucedido não volta mais à tela de conexão por causa da renderização do perfil.

## 0.4.0 — Vela Desktop

- Migração de FastAPI/Uvicorn para Vela Framework + Bottle interno.
- Janela desktop via pywebview.
- UI preservada como SPA em rota Vela `layout=blank`.
- Controllers FastAPI substituídos por `apps/zte_manager/api.py`.
- Pydantic mantido como validação na borda da API.
- Rotas `PATCH`/path params convertidas para comandos POST compatíveis com o `ApiRouter` atual.
- `ZTEBridge` adicionado para impedir hot reload de serviços stateful e preservar a sessão da ONT.
- Estrutura reorganizada em `apps/zte_manager/services`, `repositories` e `model`.
- `start.bat`, `start.ps1`, `launcher.py` e `build.bat` adicionados.
- Correções anteriores de segundo DNS/read-after-write preservadas.
- 21 testes de domínio/protocolo preservados.
