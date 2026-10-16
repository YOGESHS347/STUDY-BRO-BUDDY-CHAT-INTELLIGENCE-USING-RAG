import '@testing-library/jest-dom';

if (typeof window !== 'undefined') {
  if (window.HTMLElement) {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  }
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  }
}
