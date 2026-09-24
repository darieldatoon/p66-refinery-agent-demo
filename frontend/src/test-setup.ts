// jsdom lacks ResizeObserver, which Macaw's auto-resizing Textarea and charts use.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
