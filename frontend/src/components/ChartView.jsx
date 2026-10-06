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

const COLORS = ["#167d78", "#d49a32", "#c45c42", "#5278a5", "#718a45"];
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

function CartesianChart({ chart }) {
  const { type, data, category_key: categoryKey, value_keys: valueKeys } = chart;
  const isCombo = type === "combo";
  const Chart = isCombo ? ComposedChart : type === "bar" ? BarChart : type === "line" ? LineChart : AreaChart;
  const Series = type === "bar" ? Bar : type === "line" ? Line : Area;
  const percentFormatter = chart.percentage
    ? (value) => [`${(Number(value) * 100).toFixed(0)}%`, "Share"]
    : undefined;

  return (
    <div className="h-[260px] w-full min-w-0">
    <ResponsiveContainer width="100%" height="100%">
      <Chart
        data={data}
        stackOffset={chart.percentage ? "expand" : undefined}
        margin={{ top: 12, right: 12, left: -16, bottom: 4 }}
      >
        <CartesianGrid stroke="#d9ddd8" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={categoryKey} tick={{ fill: "#5d665f", fontSize: 11 }} />
        <YAxis
          allowDecimals={Boolean(chart.percentage)}
          domain={chart.percentage ? [0, 1] : undefined}
          tickFormatter={chart.percentage ? (value) => `${Math.round(value * 100)}%` : undefined}
          tick={{ fill: "#5d665f", fontSize: 11 }}
        />
        <Tooltip formatter={percentFormatter} />
        {valueKeys.length > 1 && <Legend />}
        {valueKeys.map((key, index) => (
          (() => {
            const seriesType = isCombo ? chart.series_types?.[key] : type;
            const SeriesComponent = seriesType === "bar" ? Bar : seriesType === "line" ? Line : Series;
            return (
              <SeriesComponent
                key={key}
                dataKey={key}
                name={key}
                {...(SeriesComponent === Bar ? {} : { type: "monotone" })}
                stackId={type === "bar" && chart.stacked ? "stacked" : undefined}
                fill={COLORS[index % COLORS.length]}
                stroke={COLORS[index % COLORS.length]}
                strokeWidth={2}
                isAnimationActive={false}
              />
            );
          })()
        ))}
      </Chart>
    </ResponsiveContainer>
    </div>
  );
}

function PieChartView({ chart }) {
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
            <Cell key={`${row[categoryKey]}-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
    </div>
  );
}

export default function ChartView({ chart }) {
  if (!chart || !TYPES[chart.type] || !Array.isArray(chart.data) || !chart.data.length) return null;
  if (!chart.category_key || !Array.isArray(chart.value_keys) || !chart.value_keys.length) return null;

  return (
    <figure className="mt-3 max-w-full overflow-hidden border-t border-ink/10 pt-3" aria-label={chartLabel(chart)}>
      <figcaption className="mb-2 text-xs font-semibold text-ink/80">
        {chart.title || TYPES[chart.type]}
      </figcaption>
      {chart.type === "pie" ? <PieChartView chart={chart} /> : <CartesianChart chart={chart} />}
    </figure>
  );
}