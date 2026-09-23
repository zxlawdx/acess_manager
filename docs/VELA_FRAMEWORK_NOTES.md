# Notas de integração com o Vela Framework

A conversão foi feita em cima do Vela Framework 0.1.0 atual do repositório `zxlawdx/Vela-framework`.

## 1. Hot reload e serviços stateful

Hoje `BaseBridge.navigate()` chama `_reload_app_modules()` e a implementação base recarrega todos os módulos cujo nome começa com `apps.`.

Isso pode recriar singletons de Service Layer em aplicações stateful, como uma sessão SSH, serial, câmera, socket ou uma `requests.Session()` autenticada em uma ONT.

### Solução usada neste projeto

`apps/zte_manager/bridge.py` herda de `BaseBridge` e sobrescreve `_reload_app_modules()` como no-op.

Não foi necessário fork do framework.

### Melhoria sugerida para o framework

Adicionar em `settings.py` algo como:

```python
HOT_RELOAD_APPS = False
```

ou restringir reload a módulos de view.

## 2. PATCH

O `ApiRouter` atual oferece:

```text
GET
POST
PUT
DELETE
```

Não há decorator `patch()`.

Neste projeto, alterações são commands `POST /.../update`, o que funciona sem alterar o framework.

Melhoria futura simples:

```python
def patch(self, path):
    def decorator(func):
        self.add_route("PATCH", path, func)
        return func
    return decorator
```

E adicionar `PATCH` ao `Access-Control-Allow-Methods` do `ApiServer`.

## 3. Parâmetros dinâmicos de rota

O Bottle aceita rotas dinâmicas, mas `_wrap_handler()` atualmente cria `wrapper()` sem `*args/**kwargs`. Portanto callbacks do tipo `/items/<id>` não recebem `id`.

Neste app os identificadores são enviados no JSON para permanecer compatível.

Uma melhoria futura do framework seria:

```python
def wrapper(**route_params):
    ...
    context["params"] = route_params
```

Assim o handler poderia ler `context["params"]`.

## 4. Status HTTP de erros

O servidor Vela serializa dict/list automaticamente, mas a API ainda não possui uma exceção de domínio equivalente a `HTTPException`.

Por isso os handlers deste app retornam:

```json
{
  "error": "mensagem",
  "type": "validation"
}
```

O `app.js` converte esse envelope em `Error` mesmo quando o HTTP é 200.

Uma evolução natural do framework seria oferecer algo como `ApiError(status, message)`.

## Decisão desta versão

Nenhuma dessas limitações exigiu alterar a ideia do Vela. A aplicação usa extensões/adapters locais e continua dependendo diretamente do framework oficial pelo GitHub.
