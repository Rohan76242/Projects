const { app, BrowserWindow, ipcMain, screen } = require("electron");
const path = require("path");

// Optimize Chromium GPU compositing for ultra-smooth fluid animation
app.commandLine.appendSwitch("enable-gpu-rasterization");
app.commandLine.appendSwitch("enable-zero-copy");
app.commandLine.appendSwitch("ignore-gpu-blocklist");

let mainWindow = null;

const CANVAS_WIDTH = 460;
const CANVAS_HEIGHT = 500;

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth } = primaryDisplay.workAreaSize;

  const initialX = Math.round((screenWidth - CANVAS_WIDTH) / 2);
  const initialY = 16; // 16px floating below top screen border

  mainWindow = new BrowserWindow({
    width: CANVAS_WIDTH,
    height: CANVAS_HEIGHT,
    x: initialX,
    y: initialY,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false, // Never drop frames when another app is focused
    },
  });

  mainWindow.setAlwaysOnTop(true, "screen-saver");
  mainWindow.loadFile(path.join(__dirname, "index.html"));

  // Initial mouse passthrough outside island
  mainWindow.setIgnoreMouseEvents(true, { forward: true });

  // Handle dynamic passthrough from renderer
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
