const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld(
  'desktop',
  Object.freeze({
    isElectron: true,
    platform: process.platform,
  }),
);
