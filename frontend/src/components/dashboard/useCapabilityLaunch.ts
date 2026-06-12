// useCapabilityLaunch — the one place capability launch behavior lives (Task 50).
//
// Shared by the launcher sheet and the contextual chips. Maps a Capability's
// launch kind to an action:
//   message       — chat.send(text)           (optimistic user bubble + streamed reply)
//   draft         — chat.setComposerDraft(text) + focus (pre-fills, user completes)
//   intent        — chat.sendCapability(id,label) (router-skipping saga dispatch)
//   link          — router.push(href)         (no chat message)
//   ephemeral_mood — chat.injectMoodPicker()  (inline mood picker card, local only)
//
// Client metric emission rule (AC-8, no double counting): the client emits
// capability_launched ONLY for message/link/draft kinds; intent-kind is emitted
// server-side by the orchestrator. The sheet-opened metric is emitted by the opener.

"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";

import { useChat } from "@/hooks/useChat";
import { track } from "@/lib/metrics";
import type { Capability } from "@/lib/capabilities";

export type LaunchSurface = "sheet" | "empty_chat" | "no_trip";

export function useCapabilityLaunch() {
  const { send, sendCapability, setComposerDraft, injectMoodPicker } = useChat();
  const router = useRouter();

  return useCallback(
    (c: Capability, surface: LaunchSurface): void => {
      const l = c.launch;

      if (l.kind === "link") {
        track("capability_launched", { id: c.id, kind: "link", surface });
        router.push(l.href);
        return;
      }

      if (l.kind === "message") {
        track("capability_launched", { id: c.id, kind: "message", surface });
        void send(l.text);
        return;
      }

      if (l.kind === "draft") {
        track("capability_launched", { id: c.id, kind: "draft", surface });
        setComposerDraft(l.text);
        return;
      }

      if (l.kind === "ephemeral_mood") {
        track("capability_launched", { id: c.id, kind: "ephemeral_mood", surface });
        injectMoodPicker();
        return;
      }

      // intent — the orchestrator emits capability_launched server-side.
      void sendCapability(l.intent, l.label);
    },
    [send, sendCapability, setComposerDraft, injectMoodPicker, router],
  );
}
