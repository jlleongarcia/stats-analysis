import { useEffect, useState } from "react";

/** Not yet in lib.dom.d.ts. */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

declare global {
  interface Window {
    /** Captured by the inline script in index.html — see the note there. */
    __installPrompt: BeforeInstallPromptEvent | null;
  }
}

const DISMISSED_KEY = "stats-analysis:install-prompt-dismissed";

function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // iOS Safari's own pre-standard flag
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/** Platforms that can install the app but never fire `beforeinstallprompt`,
 * so the user has to be told where the menu item lives. */
type ManualHint = "ios" | "macos-safari" | null;

/** Chrome, Edge and Firefox all keep "Safari" in their UA on Apple platforms,
 * so identifying Safari means ruling the others out by their own tokens. */
function isSafari(ua: string): boolean {
  return /safari/i.test(ua) && !/chrome|chromium|crios|edg|edgios|fxios|firefox|opr/i.test(ua);
}

function manualHint(): ManualHint {
  const ua = navigator.userAgent;
  // iPadOS 13+ reports itself as a Mac; touch points is what separates it.
  if (/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) {
    return "ios";
  }
  // Safari gained "Add to Dock" in version 17 (macOS Sonoma). Before that a Mac
  // could not install a web app at all, so offering instructions would be a lie.
  if (/macintosh/i.test(ua) && isSafari(ua)) {
    const major = Number(ua.match(/version\/(\d+)/i)?.[1] ?? 0);
    if (major >= 17) return "macos-safari";
  }
  return null;
}

/** A small, dismissible banner offering to install the app.
 *
 * Chrome/Edge/Android fire `beforeinstallprompt`, which we replay from our own
 * button. That event often fires before React mounts, so index.html captures it
 * into `window.__installPrompt` and notifies us via `installpromptchange`.
 *
 * Safari has no programmatic install API on either iOS or macOS and never fires
 * the event, so those get an instruction card instead — without it they get no
 * indication the app can be installed at all. On iOS that is more than a
 * convenience: WebKit evicts cached data after about a week of disuse and
 * home-screen web apps are exempt, so installing is what keeps the ~115 MB
 * Pyodide cache from being thrown away.
 */
export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(
    () => window.__installPrompt,
  );
  const [hint, setHint] = useState<ManualHint>(null);
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISSED_KEY) === "1");

  useEffect(() => {
    if (isStandalone() || dismissed) return;

    const sync = () => setDeferredPrompt(window.__installPrompt);
    window.addEventListener("installpromptchange", sync);
    // The event may have fired between render and this effect.
    sync();

    const onInstalled = () => dismiss();
    window.addEventListener("appinstalled", onInstalled);

    setHint(manualHint());

    return () => {
      window.removeEventListener("installpromptchange", sync);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, [dismissed]);

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, "1");
    setDismissed(true);
  }

  if (dismissed || isStandalone() || (!deferredPrompt && !hint)) return null;

  return (
    <div className="install-banner">
      <span className="install-banner__icon" aria-hidden="true">📊</span>
      <div className="install-banner__body">
        <strong>Install Stats Analysis</strong>
        {deferredPrompt ? (
          <span>Run your analyses from the desktop, offline, in their own window.</span>
        ) : hint === "ios" ? (
          <span>
            Tap <em>Share</em>, then <em>Add to Home Screen</em> — it then works offline.
          </span>
        ) : (
          <span>
            Choose <em>File</em> → <em>Add to Dock</em> — it then works offline.
          </span>
        )}
      </div>
      {deferredPrompt && (
        <button
          className="install-banner__button"
          onClick={async () => {
            await deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            // Single-use: the event cannot be replayed whatever the choice.
            window.__installPrompt = null;
            setDeferredPrompt(null);
            if (outcome !== "accepted") dismiss();
          }}
        >
          Install
        </button>
      )}
      <button className="install-banner__dismiss" aria-label="Dismiss" onClick={dismiss}>
        ✕
      </button>
    </div>
  );
}
