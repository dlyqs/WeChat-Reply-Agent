import { createContext, useContext } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  Bases,
  Conversation,
  Dashboard,
  Nav,
  Outbox,
  Perform,
  Preset,
  Run,
  Runtime,
  Settings,
  Setup,
  Values,
} from "./types";
export type Workspace = {
  runtime?: Runtime;
  settings?: Settings;
  setup?: Setup;
  dashboard?: Dashboard;
  bases?: Bases;
  presets: Preset[];
  runs: Run[];
  outbox: Outbox[];
  busy: boolean;
  editable: boolean;
  nav: Nav;
  navigate: (nav: Nav) => void;
  perform: Perform;
  refresh: () => Promise<void>;
  draft: Values;
  setDraft: Dispatch<SetStateAction<Values>>;
  saveSettings: () => Promise<void>;
  runtimeAction: (action: string) => Promise<void>;
  openClear: (conversation?: Conversation) => void;
  openResolve: (outbox: Outbox, resolution: "sent" | "discarded") => void;
  showRun: (run: Run) => void;
  errorMessage?: string;
};
export const WorkspaceContext = createContext<Workspace | null>(null);
export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("Workspace provider missing");
  return value;
}
