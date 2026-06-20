// bridge.js — the only channel between the webview and the organ.
// Wraps pywebview's injected api (get_state / invoke) and the Python-pushed
// "daimon:state" event. The web layer holds no authority; every action is an
// action_id routed by the Python ActionRouter.

export const bridge = {
  async getState() {
    return window.pywebview.api.get_state();
  },
  async invoke(actionId, args = {}) {
    return window.pywebview.api.invoke(actionId, args);
  },
  // Python calls: window.dispatchEvent(new CustomEvent('daimon:state',{detail:<json>}))
  onState(cb) {
    window.addEventListener("daimon:state", (e) => cb(e.detail));
  },
};
