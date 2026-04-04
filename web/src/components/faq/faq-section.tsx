"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Check,
  ChevronDown,
  ChevronUp,
  MessageSquareText,
  SkipForward,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import {
  type FaqCategoryItem,
  checkFeedbackHealth,
  fetchFaqList,
  submitFaqAction,
} from "@/lib/faq-api";

export function FaqSection() {
  const { user, isLoading: authLoading } = useAuth();
  const [items, setItems] = useState<FaqCategoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [online, setOnline] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [answerModal, setAnswerModal] = useState<string | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadFaqs = useCallback(async () => {
    try {
      const data = await fetchFaqList();
      setItems(data.items);
    } catch {
      /* silently fail — service may be offline */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkFeedbackHealth().then(setOnline);
  }, []);

  useEffect(() => {
    if (authLoading || !user || !online) {
      setLoading(false);
      return;
    }
    loadFaqs();
  }, [user, authLoading, online, loadFaqs]);

  const handleAnswer = async () => {
    if (!answerModal || !answerText.trim()) return;
    setSubmitting(true);
    try {
      await submitFaqAction(answerModal, "answer", answerText.trim());
      toast.success(`Answered "${answerModal}" — removed from FAQ`);
      setItems((prev) => prev.filter((i) => i.category !== answerModal));
      setAnswerModal(null);
      setAnswerText("");
    } catch {
      toast.error("Failed to submit answer");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSkip = async (category: string) => {
    try {
      await submitFaqAction(category, "skip");
      toast("Skipped — category will remain visible");
    } catch {
      toast.error("Failed to skip");
    }
  };

  if (!online) return null;

  return (
    <section>
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-primary" />
        <h3 className="text-lg font-semibold">FAQ Intelligence</h3>
        <span className="text-xs text-muted-foreground ml-auto">
          Questions your followers ask most
        </span>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-10">
          <MessageSquareText className="h-10 w-10 text-muted-foreground/40 mb-2" />
          <p className="text-sm text-muted-foreground">
            No unanswered FAQ categories yet
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Questions from followers will appear here, ranked by frequency.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => {
            const expanded = expandedCategory === item.category;
            return (
              <div
                key={item.category}
                className="rounded-lg border bg-card transition-all"
              >
                <div className="flex items-center gap-3 px-4 py-3">
                  <button
                    onClick={() =>
                      setExpandedCategory(expanded ? null : item.category)
                    }
                    className="flex flex-1 items-center gap-3 text-left min-w-0"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold text-sm">
                      {item.question_count}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">
                        {item.category}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {item.question_count} question
                        {item.question_count !== 1 ? "s" : ""}
                      </p>
                    </div>
                    {expanded ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                    )}
                  </button>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      size="sm"
                      onClick={() => {
                        setAnswerModal(item.category);
                        setAnswerText("");
                      }}
                    >
                      <Check className="mr-1 h-3.5 w-3.5" /> Answer
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSkip(item.category)}
                    >
                      <SkipForward className="mr-1 h-3.5 w-3.5" /> Skip
                    </Button>
                  </div>
                </div>

                {expanded && item.sample_questions.length > 0 && (
                  <div className="border-t px-4 py-3">
                    <p className="text-xs font-medium text-muted-foreground mb-2">
                      Sample questions:
                    </p>
                    <ul className="space-y-1.5">
                      {item.sample_questions.map((q, idx) => (
                        <li
                          key={idx}
                          className="text-sm text-muted-foreground flex gap-2"
                        >
                          <span className="text-muted-foreground/50 shrink-0">
                            •
                          </span>
                          <span className="italic">&ldquo;{q}&rdquo;</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Answer modal */}
      {answerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-xl mx-4">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-lg font-semibold">
                Answer: {answerModal}
              </h4>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setAnswerModal(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <p className="text-sm text-muted-foreground mb-3">
              Provide an answer for this category. Once answered, it will be
              permanently removed from the FAQ list and used to improve your
              AI&rsquo;s responses.
            </p>

            <textarea
              className="w-full min-h-[120px] rounded-lg border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
              placeholder="Type your answer here..."
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              autoFocus
            />

            <div className="flex justify-end gap-2 mt-4">
              <Button
                variant="outline"
                onClick={() => setAnswerModal(null)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleAnswer}
                disabled={submitting || !answerText.trim()}
              >
                {submitting ? "Submitting..." : "Submit Answer"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
