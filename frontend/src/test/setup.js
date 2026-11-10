import "@testing-library/jest-dom";

// antd needs matchMedia; jsdom does not provide it.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() { return false; },
  });
}

// antd Table/affix use ResizeObserver.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = window.ResizeObserver || ResizeObserverStub;
global.ResizeObserver = window.ResizeObserver;

// jsdom lacks scrollTo.
window.scrollTo = () => {};
