export function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const noop = () => null;
    const storage = {
      getItem: noop,
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
      key: () => null,
      length: 0,
    };
    if (typeof globalThis.localStorage === "undefined" || typeof globalThis.localStorage.getItem !== "function") {
      Object.defineProperty(globalThis, "localStorage", { value: storage, writable: true, configurable: true });
    }
    if (typeof globalThis.sessionStorage === "undefined" || typeof globalThis.sessionStorage.getItem !== "function") {
      Object.defineProperty(globalThis, "sessionStorage", { value: storage, writable: true, configurable: true });
    }
  }
}
