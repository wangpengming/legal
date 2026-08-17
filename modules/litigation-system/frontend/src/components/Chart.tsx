/* ECharts 封装：init + ResizeObserver 自适应 + option 热更新 + dispose。
   canvas 不吃 CSS 变量，亮/暗切换由页面订阅 theme 重算 option（themeColors）后经 setOption 刷新。 */
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

export function Chart({
  option,
  height = 300,
  className,
}: {
  option: EChartsOption;
  height?: number | string;
  className?: string;
}) {
  const elRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const optionRef = useRef(option);
  optionRef.current = option;

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    const chart = echarts.init(el);
    chartRef.current = chart;
    chart.setOption(optionRef.current, true);

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  return <div ref={elRef} className={className} style={{ width: "100%", height }} />;
}