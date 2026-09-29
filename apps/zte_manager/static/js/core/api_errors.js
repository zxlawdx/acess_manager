/* Vela API error translation: one contract for all classic-script modules.
 * Backend sends machine codes; HTTP statuses are transport evidence only.
 * This module never prints firmware bodies, URLs, credentials or raw traces.
 */
(() => {
  "use strict";
  const RULES = Object.freeze({
    AUTH_FAILED: ["authentication","As credenciais não foram aceitas. Revise o acesso.",true],
    SESSION_EXPIRED: ["session","A sessão expirou. Reconecte-se ao equipamento.",true],
    FEATURE_ABSENT: ["unsupported","O equipamento confirmou que este recurso não está disponível.",false],
    CAPABILITY_UNCONFIRMED: ["unconfirmed","Não foi possível confirmar o recurso. Verifique a sessão e refaça a identificação.",true],
    OPERATION_FORBIDDEN: ["permission","A sessão atual não tem permissão para realizar a alteração.",false],
    NETWORK_UNREACHABLE: ["connection","Não foi possível comunicar com o equipamento. Verifique a conexão.",true],
    TIMEOUT: ["timeout","A consulta demorou além do esperado. Verifique a sessão antes de repetir.",true],
    INVALID_DEVICE_RESPONSE: ["invalid_response","A resposta do equipamento não pôde ser interpretada. Nenhuma alteração foi confirmada.",true],
    OPERATION_PARTIAL: ["partial","A operação pode ter sido concluída parcialmente. Consulte o estado atual antes de repetir.",true],
    ROUTE_UNCONFIRMED: ["unconfirmed","A operação não foi localizada. Confira a versão do aplicativo e a sessão.",true],
    INVALID_INPUT: ["validation","Verifique os campos informados e tente novamente.",false],
    OPERATION_STATE: ["state","Não foi possível concluir a operação com a sessão atual.",false],
    INTERNAL_ERROR: ["internal","Ocorreu um erro interno. Consulte o suporte.",false],
    REMOTE_HTTP_ERROR: ["connection","O equipamento ou serviço recusou a comunicação.",true]
  });
  const CODE_BY_TYPE = Object.freeze({
    authentication:"AUTH_FAILED", session:"SESSION_EXPIRED",
    session_expired:"SESSION_EXPIRED", unsupported:"CAPABILITY_UNCONFIRMED",
    unconfirmed:"CAPABILITY_UNCONFIRMED", permission:"OPERATION_FORBIDDEN",
    connection:"NETWORK_UNREACHABLE", timeout:"TIMEOUT",
    invalid_response:"INVALID_DEVICE_RESPONSE", partial:"OPERATION_PARTIAL",
    validation:"INVALID_INPUT", internal:"INTERNAL_ERROR", state:"OPERATION_STATE"
  });
  const PRIVATE_CONTENT = /(?:https?:\/\/|\/api\/|\b(?:password|passwd|secret|token|cookie|senha)\b|[{}<>]|\b(?:GET|POST|PUT|PATCH|DELETE)\s+\/|traceback|typeerror|attributeerror)/i;
  const SAFE_LABEL = /^[\p{L}\p{N}.,():;_\-!? \n]{1,150}$/u;
  function safeText(value) {
    return typeof value === "string" && SAFE_LABEL.test(value) &&
      !PRIVATE_CONTENT.test(value) ? value.trim() : "";
  }
  function mapStatus(status, rejected = false) {
    if (status === 401) return "AUTH_FAILED";
    if (status === 403) return "OPERATION_FORBIDDEN";
    if (status === 404 || status === 405) return "ROUTE_UNCONFIRMED";
    if (status === 408 || status === 504) return "TIMEOUT";
    if (status >= 500) return "INTERNAL_ERROR";
    if (status >= 400) return "OPERATION_STATE";
    return rejected ? "INVALID_DEVICE_RESPONSE" : "NETWORK_UNREACHABLE";
  }
  class OperationError extends Error {
    constructor(code, options={}) {
      const known = Object.hasOwn(RULES, code) ? code : "OPERATION_STATE";
      const [kind, defaultMessage, retryable] = RULES[known];
      const backendMessage = (kind === "validation" || kind === "state")
        ? safeText(options.error) : "";
      let message = backendMessage || defaultMessage;
      if (known === "INTERNAL_ERROR" && /^[0-9a-f]{32}$/i.test(options.error_id || "")) {
        message += " Código: " + options.error_id + ".";
      }
      if (known === "OPERATION_PARTIAL" &&
          Number.isSafeInteger(options.completed) && Number.isSafeInteger(options.total) &&
          options.completed >= 0 && options.total >= options.completed) {
        message += " Etapas concluídas: " + options.completed + " de " + options.total + ".";
      }
      super(message);
      this.name="OperationError";
      this.code=known;this.kind=kind;this.retryable=Boolean(options.retryable ?? retryable);
      this.status=options.status || 0;
      this.completed=known==="OPERATION_PARTIAL" ? options.completed : undefined;
      this.total=known==="OPERATION_PARTIAL" ? options.total : undefined;
    }
  }
  function fromPayload(body, {status=0}={}) {
    const payload=body && typeof body==="object" && !Array.isArray(body)
      ? body : {};
    // Never interpret a raw 404 as a firmware feature missing. Only the
    // backend's explicitly verified FEATURE_ABSENT code may say that.
    const claimed=typeof payload.code==="string" ? payload.code : "";
    const legacyType=typeof payload.type==="string" ? payload.type : "";
    let code = Object.hasOwn(RULES,claimed) ? claimed :
      (Object.hasOwn(CODE_BY_TYPE,legacyType) ? CODE_BY_TYPE[legacyType] :
        mapStatus(status,true));
    if (code==="FEATURE_ABSENT" && claimed!=="FEATURE_ABSENT")
      code="CAPABILITY_UNCONFIRMED";
    if ((status===404 || status===405) && code==="FEATURE_ABSENT" &&
        claimed!=="FEATURE_ABSENT") code="ROUTE_UNCONFIRMED";
    return new OperationError(code,{...payload,status});
  }
  function fromThrown(error) {
    if (error instanceof OperationError) return error;
    if (error && error.name==="AbortError") {
      const wrapped = new OperationError("TIMEOUT");
      wrapped.name="AbortError"; // preserve discovery cancellation branch
      return wrapped;
    }
    if ((error instanceof TypeError || error?.name === "TypeError") &&
        /fetch|network|load failed/i.test(error.message||"")) {
      return new OperationError("NETWORK_UNREACHABLE");
    }
    return new OperationError("OPERATION_STATE");
  }
  function ensureObject(value) {
    if (value === null || typeof value!=="object" || Array.isArray(value)) {
      throw new OperationError("INVALID_DEVICE_RESPONSE");
    }
    return value;
  }
  const facade=Object.freeze({
    RULES, OperationError, fromPayload, fromThrown, ensureObject, safeText, mapStatus
  });
  if(typeof window!=="undefined") window.AccessManagerErrors=facade;
})();