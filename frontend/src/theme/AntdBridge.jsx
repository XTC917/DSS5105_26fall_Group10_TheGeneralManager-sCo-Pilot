import { ConfigProvider, theme as antdTheme } from "antd";
import { ACCENTS } from "./themeConfig.js";
import { useTheme } from "./useTheme.js";

const ACCENT_HEX = Object.fromEntries(ACCENTS.map((item) => [item.id, item.swatch]));

/**
 * Bridges the SweaterCo theme system to Ant Design (used by the admin pages
 * and @ant-design/icons). Ant Design components are not widely used today, but
 * this keeps them consistent with Light/Dark and the active accent.
 */
export function AntdBridge({ children }) {
  const { resolvedMode, accent } = useTheme();
  const isDark = resolvedMode === "dark";
  const colorPrimary = ACCENT_HEX[accent] || "#1d4ed8";

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary,
          colorInfo: colorPrimary,
          colorLink: colorPrimary,
          borderRadius: 10,
          borderRadiusLG: 14,
          fontFamily:
            "IBM Plex Sans, Inter, -apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif",
          fontSize: 14,
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
}
