const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  setWindowSize: (width, height) => ipcRenderer.send("resize-window", { width, height }),
  setIgnoreMouseEvents: (ignore, forward) => ipcRenderer.send("set-ignore-mouse-events", { ignore, forward }),
  closeApp: () => ipcRenderer.send("close-app"),
  minimizeApp: () => ipcRenderer.send("minimize-app"),
  blurWindow: () => ipcRenderer.send("blur-window"),
});
