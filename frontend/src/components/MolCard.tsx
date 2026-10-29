import { useState } from "react";
import { CheckCircle, XCircle, AlertTriangle, Atom, Copy, Check } from "lucide-react";
import { cn, fmt, scoreColor, dockingColor } from "../lib/utils";
import type { MoleculeResult } from "../api/client";
import { DruglikenessRadar } from "./DruglikenessRadar";

interface MolCardProps {
  mol: MoleculeResult;
  onSelectPose?: () => void;
}

export function MolCard({ mol, onSelectPose }: MolCardProps) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-100 truncate">
            #{mol.rank} {mol.name}
          </h3>
          <SmilesRow smiles={mol.smiles} />
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {mol.lipinski?.passes_ro5 ? (
            <span className="flex items-center gap-1 text-emerald-400 text-xs">
              <CheckCircle size={12} /> Ro5 pass
            </span>
          ) : (
            <span className="flex items-center gap-1 text-red-400 text-xs">
              <XCircle size={12} /> Ro5 fail
            </span>
          )}
          {mol.lipinski && !mol.lipinski.passes_pains && (
            <span className="flex items-center gap-1 text-amber-400 text-xs">
              <AlertTriangle size={12} /> PAINS alert
            </span>
          )}
        </div>
      </div>

      {/* Body: structure | scores | radar */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* 2D Structure */}
        {mol.svg_2d ? (
          <div
            className="rounded-lg bg-white p-1.5 shrink-0 self-start overflow-hidden flex items-center justify-center w-52 h-52 [&>svg]:w-full [&>svg]:h-full"
            dangerouslySetInnerHTML={{ __html: mol.svg_2d }}
          />
        ) : (
          <div className="flex items-center justify-center rounded-lg bg-slate-700 shrink-0 self-start w-52 h-52">
            <Atom className="text-slate-500" size={32} />
          </div>
        )}

        {/* Scores */}
        <div className="flex flex-col gap-2 flex-1 min-w-[200px]">
          <ScoreRow
            label="Ensemble Score"
            value={fmt(mol.ensemble_score, 3)}
            className={scoreColor(mol.ensemble_score)}
          />
          <ScoreRow
            label="Chemprop pIC50"
            value={
              mol.predicted_pic50 != null
                ? `${fmt(mol.predicted_pic50, 3)} ± ${fmt(mol.pic50_uncertainty, 3)}`
                : "—"
            }
            className={scoreColor(mol.predicted_pic50)}
          />
          <ScoreRow
            label="DeepChem pIC50"
            value={fmt(mol.deepchem_score, 3)}
            className={scoreColor(mol.deepchem_score)}
          />
          <ScoreRow
            label="Docking Score"
            value={
              mol.docking_score != null ? `${fmt(mol.docking_score, 2)} kcal/mol` : "—"
            }
            className={dockingColor(mol.docking_score)}
          />
          {mol.has_pose && onSelectPose && (
            <button
              onClick={onSelectPose}
              className="mt-auto w-full py-2 rounded-lg bg-blue-600/20 border border-blue-600/50 text-blue-300 text-xs font-semibold hover:bg-blue-600/30 transition-colors"
            >
              View 3D Docking Pose
            </button>
          )}
        </div>

        {/* Radar chart */}
        {mol.lipinski && (
          <div className="w-full md:w-52 shrink-0 rounded-lg bg-slate-800/40 border border-slate-700/50 p-1">
            <DruglikenessRadar lipinski={mol.lipinski} />
          </div>
        )}
      </div>

      {/* Lipinski properties grid */}
      {mol.lipinski && (
        <div className="grid grid-cols-3 gap-2 text-xs">
          {[
            { label: "MW", val: `${mol.lipinski.mw.toFixed(1)} Da` },
            { label: "LogP", val: mol.lipinski.logp.toFixed(2) },
            { label: "TPSA", val: `${mol.lipinski.tpsa.toFixed(1)} Å²` },
            { label: "HBD", val: String(mol.lipinski.hbd) },
            { label: "HBA", val: String(mol.lipinski.hba) },
            { label: "RotBonds", val: String(mol.lipinski.rotatable_bonds) },
          ].map((p) => (
            <div key={p.label} className="rounded bg-slate-700/50 px-2 py-1">
              <p className="text-slate-500">{p.label}</p>
              <p className="font-mono font-semibold text-slate-200">{p.val}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ScoreRow({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="flex justify-between items-center rounded bg-slate-700/40 px-2.5 py-1.5">
      <span className="text-xs text-slate-400">{label}</span>
      <span className={cn("text-xs font-mono font-bold", className)}>{value}</span>
    </div>
  );
}

function SmilesRow({ smiles }: { smiles: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(smiles);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — selection still possible */
    }
  };
  return (
    <button
      onClick={copy}
      title="Click to copy SMILES"
      className="group flex items-center gap-1.5 mt-0.5 max-w-full text-left"
    >
      <span className="text-[11px] font-mono text-slate-500 truncate group-hover:text-slate-300 transition-colors">
        {smiles.length > 60 ? smiles.slice(0, 60) + "…" : smiles}
      </span>
      {copied ? (
        <Check size={11} className="text-emerald-400 shrink-0" />
      ) : (
        <Copy
          size={11}
          className="text-slate-600 group-hover:text-slate-400 shrink-0 transition-colors"
        />
      )}
    </button>
  );
}
