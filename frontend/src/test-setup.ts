import "@testing-library/jest-dom";

// Recharts uses ResizeObserver internally via ResponsiveContainer.
// jsdom does not implement it, so we provide a minimal stub so charts render.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
