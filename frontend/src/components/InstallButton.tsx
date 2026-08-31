import { useEffect, useState } from "react";

/**
 * Chrome/Edge only surface the install affordance as a small omnibox icon that
 * most people never notice, so offer an explicit button instead.
 *
 * `beforeinstallprompt` fires once the browser considers the app installable
 * (secure context + manifest + a service worker with a fetch handler). It never
 * fires on Firefox or iOS Safari, and never when the app is already installed —
 * in those cases we render nothing rather than a button that cannot work.
 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function InstallButton() {
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      // Without this the browser shows its own mini-infobar instead of letting
      // us choose the moment.
      e.preventDefault();
      setPrompt(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setPrompt(null);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed || !prompt) return null;

  return (
    <button
      className="btn btn--install"
      title="Install this app on your computer so it opens in its own window and works offline"
      onClick={async () => {
        await prompt.prompt();
        // The event is single-use: whatever the choice, it cannot be replayed.
        await prompt.userChoice;
        setPrompt(null);
      }}
    >
      Install app
    </button>
  );
}
