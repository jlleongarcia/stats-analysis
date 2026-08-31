import { useRef, useState } from "react";

interface Props {
  onFile: (file: File) => void;
  busy?: boolean;
}

const ACCEPT = ".csv,.tsv,.txt,.xlsx,.xls,.xlsm,.ods";

export function FileDrop({ onFile, busy }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div
      className={`filedrop ${over ? "filedrop--over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      onClick={() => input.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
    >
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      <strong>{busy ? "Reading file…" : "Drop a CSV or Excel file here"}</strong>
      <span className="muted">or click to choose · nothing leaves your device</span>
    </div>
  );
}
