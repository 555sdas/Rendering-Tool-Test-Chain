const path = require('node:path');
const { app, BrowserWindow, session, shell } = require('electron');

const DEV_SERVER_URL = process.env.ELECTRON_START_URL || 'http://localhost:5173';
const DEV_SERVER_ORIGIN = new URL(DEV_SERVER_URL).origin;

let mainWindow = null;
let retryTimer = null;

function isAllowedAppUrl(rawUrl) {
  try {
    return new URL(rawUrl).origin === DEV_SERVER_ORIGIN;
  } catch {
    return false;
  }
}

function openExternalUrl(rawUrl) {
  try {
    const url = new URL(rawUrl);
    if (url.protocol === 'https:' || url.protocol === 'http:') {
      void shell.openExternal(url.toString());
    }
  } catch {
    // Ignore invalid URLs instead of handing them to the operating system.
  }
}

function loadRenderer(window) {
  void window.loadURL(DEV_SERVER_URL).catch(() => {
    if (window.isDestroyed()) return;
    retryTimer = setTimeout(() => loadRenderer(window), 1000);
  });
}

function createMainWindow() {
  const window = new BrowserWindow({
    title: 'XR 渲染测试平台',
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    autoHideMenuBar: process.platform !== 'darwin',
    backgroundColor: '#f5f7fa',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  window.once('ready-to-show', () => {
    window.show();
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    openExternalUrl(url);
    return { action: 'deny' };
  });

  const preventExternalNavigation = (event, url) => {
    if (!isAllowedAppUrl(url)) {
      event.preventDefault();
      openExternalUrl(url);
    }
  };

  window.webContents.on('will-navigate', preventExternalNavigation);
  window.webContents.on('will-redirect', preventExternalNavigation);

  window.on('closed', () => {
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    if (mainWindow === window) {
      mainWindow = null;
    }
  });

  loadRenderer(window);
  return window;
}

const hasSingleInstanceLock = app.requestSingleInstanceLock();

if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });

  app.whenReady().then(() => {
    session.defaultSession.setPermissionCheckHandler(() => false);
    session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
      callback(false);
    });
    mainWindow = createMainWindow();

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        mainWindow = createMainWindow();
      }
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });
}
