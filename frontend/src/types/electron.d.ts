export {};

declare global {
  interface Window {
    desktop?: Readonly<{
      isElectron: true;
      platform: string;
    }>;
  }
}
