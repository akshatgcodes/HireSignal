import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { findCard, followUp, moveCard, shortDate, type Columns } from "../lib/board";
import { STATUSES, type Application, type Status } from "../types";

const TITLES: Record<Status, string> = { applied: "Applied", interview: "Interview", offer: "Offer", rejected: "Rejected" };

// dnd-kit ids: cards are numbers, columns are "col:<status>"
const colId = (s: Status) => `col:${s}`;
const statusOf = (id: string | number): Status | null =>
  typeof id === "string" && id.startsWith("col:") ? (id.slice(4) as Status) : null;

function Card({ app, onOpen, dragging }: { app: Application; onOpen?: () => void; dragging?: boolean }) {
  const due = app.status === "applied" || app.status === "interview" ? followUp(app.follow_up_on) : null;
  return (
    <div className={`card${dragging ? " dragging" : ""}`}>
      <button className="card-open" onClick={onOpen} onPointerDown={(e) => e.stopPropagation()} aria-label={`Edit ${app.role} at ${app.company}`}>
        ✎
      </button>
      <div className="card-company">{app.company}</div>
      <div className="card-role">{app.role}</div>
      <div className="card-meta">
        {app.team && <span className="chip">{app.team}</span>}
        <span title="Applied on">{shortDate(app.applied_on)}</span>
      </div>
      {due && <div className={`due ${due.tone}`}>{due.label}</div>}
    </div>
  );
}

function SortableCard({ app, onOpen }: { app: Application; onOpen: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: app.id });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.35 : 1 }}
      {...attributes}
      {...listeners}
      aria-roledescription="draggable card"
    >
      <Card app={app} onOpen={onOpen} />
    </li>
  );
}

function Column({ status, cards, onOpen, onAdd }: { status: Status; cards: Application[]; onOpen: (a: Application) => void; onAdd: () => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: colId(status) });
  return (
    <section className={`column ${status}${isOver ? " over" : ""}`} aria-label={TITLES[status]}>
      <header className="column-head">
        <h2>{TITLES[status]}</h2>
        <span className="muted">{cards.length}</span>
        <button className="icon-btn" onClick={onAdd} aria-label={`Add to ${TITLES[status]}`} title="Add application">
          +
        </button>
      </header>
      <SortableContext items={cards.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        <ul ref={setNodeRef} className="cards">
          {cards.map((a) => (
            <SortableCard key={a.id} app={a} onOpen={() => onOpen(a)} />
          ))}
          {!cards.length && <li className="empty-col muted">Drop here</li>}
        </ul>
      </SortableContext>
    </section>
  );
}

export default function Kanban({
  columns,
  setColumns,
  onMove,
  onOpen,
  onAdd,
}: {
  columns: Columns;
  setColumns: (c: Columns) => void;
  onMove: (id: number, status: Status, index: number) => void;
  onOpen: (a: Application) => void;
  onAdd: (s: Status) => void;
}) {
  const [active, setActive] = useState<Application | null>(null);
  const [origin, setOrigin] = useState<{ status: Status; index: number } | null>(null);
  const [before, setBefore] = useState<Columns | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Where a drop over `overId` should land: an empty column's end, or the hovered card's slot
  const target = (cols: Columns, overId: string | number): { status: Status; index: number } | null => {
    const col = statusOf(overId);
    if (col) return { status: col, index: cols[col].length };
    return findCard(cols, Number(overId));
  };

  const onDragStart = (e: DragStartEvent) => {
    const at = findCard(columns, Number(e.active.id));
    if (!at) return;
    setActive(columns[at.status][at.index]);
    setOrigin(at);
    setBefore(columns);
  };

  // Moving into another column happens while hovering, so the card visibly joins it
  const onDragOver = (e: DragOverEvent) => {
    if (!e.over) return;
    const from = findCard(columns, Number(e.active.id));
    const to = target(columns, e.over.id);
    if (from && to && from.status !== to.status) setColumns(moveCard(columns, Number(e.active.id), to.status, to.index));
  };

  const onDragEnd = (e: DragEndEvent) => {
    const id = Number(e.active.id);
    setActive(null);
    const from = findCard(columns, id);
    if (!from || !e.over) return;
    const to = target(columns, e.over.id) ?? from;
    const next = to.status === from.status && to.index !== from.index ? moveCard(columns, id, to.status, to.index) : columns;
    if (next !== columns) setColumns(next);
    const final = findCard(next, id)!;
    if (!origin || origin.status !== final.status || origin.index !== final.index) onMove(id, final.status, final.index);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
      onDragCancel={() => {
        // Undo any cross-column preview from onDragOver
        setActive(null);
        if (before) setColumns(before);
      }}
    >
      <div className="kanban">
        {STATUSES.map((s) => (
          <Column key={s} status={s} cards={columns[s]} onOpen={onOpen} onAdd={() => onAdd(s)} />
        ))}
      </div>
      <DragOverlay>{active ? <Card app={active} dragging /> : null}</DragOverlay>
    </DndContext>
  );
}
