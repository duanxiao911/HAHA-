"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { CommunityActions, CommunityContextValue } from "./contract";
import { createLocalCommunityAdapter } from "./local-adapter";

const CommunityContext = createContext<CommunityContextValue | null>(null);

export function CommunityProvider({ children }: { children: ReactNode }) {
  const [adapter] = useState(() => createLocalCommunityAdapter());
  const [snapshot, setSnapshot] = useState(() => adapter.getSnapshot());

  useEffect(() => {
    const unsubscribe = adapter.subscribe(() => setSnapshot(adapter.getSnapshot()));
    adapter.hydrate();
    return () => {
      unsubscribe();
      adapter.dispose();
    };
  }, [adapter]);

  const actions = useMemo<CommunityActions>(() => ({
    getFeed: (query, signal) => adapter.getFeed(query, signal),
    getContent: (contentId, signal) => adapter.getContent(contentId, signal),
    search: (query, signal) => adapter.search(query, signal),
    setReaction: (contentId, reaction, active) => adapter.setReaction(contentId, reaction, active),
    setPersonFollow: (personId, active) => adapter.setPersonFollow(personId, active),
    recordWatchHistory: (contentId, progressSeconds) => adapter.recordWatchHistory(contentId, progressSeconds),
    removeWatchHistory: (contentId) => adapter.removeWatchHistory(contentId),
    clearWatchHistory: () => adapter.clearWatchHistory(),
    createComment: (input) => adapter.createComment(input),
    deleteOwnComment: (commentId) => adapter.deleteOwnComment(commentId),
    createTimedAnnotation: (input) => adapter.createTimedAnnotation(input),
    deleteOwnTimedAnnotation: (annotationId) => adapter.deleteOwnTimedAnnotation(annotationId),
    markNotificationRead: (notificationId) => adapter.markNotificationRead(notificationId),
    markAllNotificationsRead: () => adapter.markAllNotificationsRead(),
    deleteNotification: (notificationId) => adapter.deleteNotification(notificationId),
    rememberSearchTerm: (term) => adapter.rememberSearchTerm(term),
    removeSearchTerm: (term) => adapter.removeSearchTerm(term),
    clearSearchHistory: () => adapter.clearSearchHistory(),
    createSubmissionDraft: (input) => adapter.createSubmissionDraft(input),
    updateSubmissionDraft: (draftId, patch) => adapter.updateSubmissionDraft(draftId, patch),
    transitionSubmissionDraft: (draftId, nextStatus, reviewerNote) => adapter.transitionSubmissionDraft(draftId, nextStatus, reviewerNote),
    deleteSubmissionDraft: (draftId) => adapter.deleteSubmissionDraft(draftId),
    resetLocalDemoState: () => adapter.resetLocalDemoState(),
  }), [adapter]);

  const value = useMemo<CommunityContextValue>(() => ({
    snapshot,
    actions,
    unreadNotificationCount: snapshot.notifications.filter((notification) => !notification.readAt).length,
  }), [actions, snapshot]);

  return <CommunityContext.Provider value={value}>{children}</CommunityContext.Provider>;
}

export function useCommunity(): CommunityContextValue {
  const context = useContext(CommunityContext);
  if (!context) throw new Error("useCommunity 必须在 CommunityProvider 内使用");
  return context;
}
