import '@testing-library/jest-dom/vitest';

// jsdom has neither: React Flow (used by the Workflow tab's diagram) reads
// both while measuring its container and node handles. Minimal stand-ins —
// not full implementations — are enough for it to lay nodes out in tests.
// (jsdom also reports every element as 0×0 via getBoundingClientRect, which
// React Flow needs a plausible size from — that stub is scoped to the
// diagram's own test files instead of set globally here, so it can't mask a
// real zero-size regression in an unrelated layout test.)
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
