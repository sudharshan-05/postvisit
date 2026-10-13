"use client";

import React, { useState } from "react";
import { CheckCircle2, Circle, MoreVertical, Plus } from "lucide-react";
import { RecoveryPlanTask } from "@/types";
import { patientApi } from "@/lib/api/patient";
import { toast } from "sonner";

interface RecoveryChecklistProps {
  tasks?: RecoveryPlanTask[];
  consultationId?: string;
}

export function RecoveryChecklist({
  tasks,
  consultationId = "default-consultation",
}: RecoveryChecklistProps) {
  const [items, setItems] = useState<RecoveryPlanTask[]>(tasks || []);

  // Sync when tasks prop changes
  React.useEffect(() => {
    if (tasks && tasks.length > 0) {
      setItems(tasks);
    } else {
      // Fetch directly from backend if not provided as props
      patientApi
        .getRecoveryPlan(consultationId)
        .then((plan) => {
          if (plan?.tasks) setItems(plan.tasks);
        })
        .catch(() => {});
    }
  }, [tasks, consultationId]);


  const toggleItem = async (taskKey: string) => {
    const updated = items.map((item) =>
      item.task_key === taskKey ? { ...item, completed: !item.completed } : item
    );
    setItems(updated);

    const target = updated.find((i) => i.task_key === taskKey);
    try {
      await patientApi.toggleRecoveryTask(
        consultationId,
        taskKey,
        target?.completed || false
      );
      toast.success(
        target?.completed ? "Task marked complete!" : "Task updated"
      );
    } catch {
      // Keep optimistic state in UI for seamless patient tracking
    }
  };

  return (
    <div className="rounded-3xl border border-[#E3ECE9] bg-white p-6 shadow-xs">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#F1F5F9]">
        <h3 className="text-sm font-bold text-[#172B28]">Action Items & Notes</h3>
        <button
          className="rounded-lg p-1 text-[#5F736F] hover:bg-[#F7F9F8] transition"
          aria-label="More options"
        >
          <MoreVertical className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-3">
        {items.length === 0 ? (
          <p className="text-xs text-[#5F736F] italic py-2">
            No pending recovery action items documented for this visit.
          </p>
        ) : (
          items.map((task) => (
            <button
              key={task.task_key}
              onClick={() => toggleItem(task.task_key)}
              className="flex items-center gap-3 w-full text-left py-1 hover:bg-[#F8FAFC] px-2 rounded-xl transition"
            >
              {task.completed ? (
                <CheckCircle2 className="h-5 w-5 text-[#2563EB] shrink-0 fill-blue-50" />
              ) : (
                <Circle className="h-5 w-5 text-[#CBD5E1] shrink-0" />
              )}
              <span
                className={`text-xs font-medium transition ${
                  task.completed
                    ? "text-[#5F736F] line-through decoration-slate-300"
                    : "text-[#172B28]"
                }`}
              >
                {task.title}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
