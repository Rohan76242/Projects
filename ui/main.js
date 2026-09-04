const { app, BrowserWindow, ipcMain, screen } = require("electron");
const path = require("path");

// Optimize for high-refresh 120 FPS and smooth compositing
app.commandLine.appendSwitch("enable-gpu-rasterization");
app.commandLine.appendSwitch("enable-zero-copy");
app.commandLine.appendSwitch("ignore-gpu-blocklist");

let mainWindow = null;

const COLLAPSED_WIDTH = 260;
const COLLAPSED_HEIGHT = 64;

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;

  const initialX = Math.round((screenWidth - COLLAPSED_WIDTH) / 2);
  const initialY = 24; // Floating 24px below screen top

  mainWindow = new BrowserWindow({
    width: COLLAPSED_WIDTH,
    height: COLLAPSED_HEIGHT,
    x: initialX,
    y: initialY,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.setAlwaysOnTop(true, "screen-saver");
  mainWindow.loadFile(path.join(__dirname, "index.html"));

  // Handle Dynamic Island Resize & Center Anchor
  ipcMain.on("resize-window", (event, { width, height }) => {
    if (!mainWindow) return;
    const currentBounds = mainWindow.getBounds();
    // Maintain horizontal center when expanding/collapsing
    const newX = Math.round(currentBounds.x + (currentBounds.width - width) / 2);
    mainWindow.setBounds({
      x: newX,
      y: currentBounds.y,
      width: Math.round(width),
      height: Math.round(height),
    });
  });

  // Handle Click-Through Passthrough
  ipcMain.on("set-ignore-mouse-events", (event, { ignore, forward }) => {
    if (!mainWindow) return;
    mainWindow.setIgnoreMouseEvents(ignore, { forward: forward || false });
  });

  ipcMain.on("close-app", () => {
    app.quit();
  });

  ipcMain.on("minimize-app", () => {
    if (mainWindow) mainWindow.minimize();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
