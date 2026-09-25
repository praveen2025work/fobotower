import '@testing-library/jest-dom/vitest';

// jsdom has neither: React Flow (used by the Workflow tab's diagram) reads
// both while measuring its container and node handles. Minimal stand-ins —
// not full implementations — are enough for it to lay nodes out in tests.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
  globalThis.DOMMatrixReadOnly = class DOMMatrixReadOnly {
    constructor(transform) {
      const scale = /scale\(([0-9.]+)\)/.exec(transform || '')?.[1];
      this.m22 = scale ? Number(scale) : 1;
    }
  };
}

// jsdom reports every element as 0×0. React Flow refuses to lay out nodes in
// a zero-size container, so give every element a plausible size by default.
if (!Element.prototype.getBoundingClientRect.__fobo_stub) {
  const stub = function getBoundingClientRect() {
    return {
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 1024,
      bottom: 640,
      width: 1024,
      height: 640,
      toJSON() {},
    };
  };
  stub.__fobo_stub = true;
  Element.prototype.getBoundingClientRect = stub;
}
