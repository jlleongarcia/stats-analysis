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
  // Safari on macOS is a dead end for this app. "Add to Dock" (Safari 17+)
  // creates a standalone window, but tested against this build it does not keep
  // the Pyodide cache, so the app cannot start without a network -- which is the
  // whole point of installing it. Point those users at Chrome/Edge instead.
  if (/macintosh/i.test(ua) && isSafari(ua)) return "macos-safari";
  return null;
}

/** A small, dismissible banner offering to install the app.
 *
 * Chrome/Edge/Android fire `beforeinstallprompt`, which we replay from our own
 * button. That event often fires before React mounts, so index.html captures it
 * into `window.__installPrompt` and notifies us via `installpromptchange`.
 *
 * Safari has no programmatic install API and never fires the event, so it gets
 * an instruction card instead. The two Safaris need different advice: on iOS,
 * Add to Home Screen genuinely works (and is what stops WebKit evicting the
 * ~115 MB Pyodide cache after a week of disuse); on macOS, Add to Dock does not
 * survive offline, so the card sends those users to Chrome or Edge.
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
            Open this page in <em>Chrome</em> or <em>Edge</em> to install it. Safari's{" "}
            <em>Add to Dock</em> does not keep the engine cached, so it will not work offline.
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
