import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartTooltip, useChartTheme } from "./chartTheme.jsx";

const PAGE_SIZE = 50;
const TYPES = {
  bar: "Bar chart",
  pie: "Pie chart",
  line: "Line chart",
  area: "Area chart",
  combo: "Bar and line chart",
};

function chartLabel(chart) {
  if (chart.type === "bar" && chart.percentage) return "100% stacked bar chart";
  return chart.type === "bar" && chart.stacked ? "Stacked bar chart" : TYPES[chart.type];
}

function CartesianChart({ chart, theme }) {
  const { type, data, category_key: categoryKey, value_keys: valueKeys } = chart;
  const isCombo = type === "combo";
  const Chart = isCombo ? ComposedChart : type === "bar" ? BarChart : type === "line" ? LineChart : AreaChart;
  const Series = type === "bar" ? Bar : type === "line" ? Line : Area;
  const percentFormatter = chart.percentage
    ? (value) => [`${(Number(value) * 100).toFixed(0)}%`, "Share"]
    : undefined;
  const tick = { fill: theme.axis, fontSize: 11 };

  return (
    <div className="h-[260px] w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <Chart
          data={data}
          stackOffset={chart.percentage ? "expand" : undefined}
          margin={{ top: 12, right: 12, left: -8, bottom: 4 }}
        >
          <CartesianGrid stroke={theme.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={categoryKey} tick={tick} axisLine={{ stroke: theme.grid }} tickLine={false} />
          <YAxis
            allowDecimals={Boolean(chart.percentage)}
            domain={chart.percentage ? [0, 1] : undefined}
            tickFormatter={chart.percentage ? (value) => `${Math.round(value * 100)}%` : undefined}
            tick={tick}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<ChartTooltip formatter={percentFormatter} />} />
          {valueKeys.length > 1 && (
            <Legend wrapperStyle={{ fontSize: 11, color: theme.legend }} />
          )}
          {valueKeys.map((key, index) => {
            const seriesType = isCombo ? chart.series_types?.[key] : type;
            const SeriesComponent = seriesType === "bar" ? Bar : seriesType === "line" ? Line : Series;
            const color = theme.colors[index % theme.colors.length];
            return (
              <SeriesComponent
                key={key}
                dataKey={key}
                name={key}
                {...(SeriesComponent === Bar ? { radius: [4, 4, 0, 0] } : { type: "monotone" })}
                stackId={type === "bar" && chart.stacked ? "stacked" : undefined}
                fill={color}
                stroke={color}
                strokeWidth={2}
                isAnimationActive={false}
              />
            );
          })}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

function PieChartView({ chart, theme }) {
  const { data, category_key: categoryKey, value_keys: valueKeys } = chart;

  return (
    <div className="h-[260px] w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKeys[0]}
            nameKey={categoryKey}
            cx="50%"
            cy="48%"
            outerRadius={88}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            isAnimationActive={false}
          >
            {data.map((row, index) => (
              <Cell key={`${row[categoryKey]}-${index}`} fill={theme.colors[index % theme.colors.length]} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ChartView({ chart }) {
  const [page, setPage] = useState(0);
  const theme = useChartTheme();
  useEffect(() => {
    setPage(0);
  }, [chart]);

  if (!chart || !TYPES[chart.type] || !Array.isArray(chart.data) || !chart.data.length) return null;
  if (!chart.category_key || !Array.isArray(chart.value_keys) || !chart.value_keys.length) return null;

  const pageCount = Math.max(1, Math.ceil(chart.data.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const pageChart = pageCount === 1
    ? chart
    : {
        ...chart,
        data: chart.data.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE),
      };

  return (
    <figure
      className="mt-3 w-full min-w-0 max-w-full overflow-hidden rounded-card border border-line bg-surface p-3 shadow-xs sm:p-4"
      aria-label={chartLabel(chart)}
    >
      <figcaption className="mb-2 type-caption font-semibold text-foreground">
        {chart.title || TYPES[chart.type]}
      </figcaption>
      {chart.type === "pie" ? (
        <PieChartView chart={pageChart} theme={theme} />
      ) : (
        <CartesianChart chart={pageChart} theme={theme} />
      )}
      {pageCount > 1 && (
        <div className="mt-2 flex items-center justify-between type-caption text-muted">
          <span>
            {currentPage * PAGE_SIZE + 1}–{Math.min(chart.data.length, currentPage * PAGE_SIZE + PAGE_SIZE)} of {chart.data.length}
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}
              className="rounded-control border border-line px-2 py-1 hover:bg-surfaceMuted disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={currentPage >= pageCount - 1}
              onClick={() => setPage(currentPage + 1)}
              className="rounded-control border border-line px-2 py-1 hover:bg-surfaceMuted disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </figure>
  );
}
