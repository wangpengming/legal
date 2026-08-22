/** F5 预设库输入框：法院/案由输入时从预设库给出高频建议（datalist）。 */
import { useQuery } from "@tanstack/react-query";
import { presetApi, Preset } from "../lib/api";

interface Props {
  kind: "court" | "cause";
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export default function PresetInput({ kind, value, onChange, placeholder }: Props) {
  // 预设列表按 usage_count 排序（高频在前），随输入即时过滤
  const { data: presets = [] } = useQuery<Preset[]>({
    queryKey: ["presets", kind],
    queryFn: () => presetApi.list(kind),
  });
  const listId = `${kind}-presets`;
  const filtered = value
    ? presets.filter(p => p.value.includes(value))
    : presets;

  return (
    <>
      <input
        className="form-input"
        list={listId}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
      />
      <datalist id={listId}>
        {filtered.map(p => (
          <option key={p.id} value={p.value} />
        ))}
      </datalist>
    </>
  );
}