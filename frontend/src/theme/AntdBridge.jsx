import { ConfigProvider, theme as antdTheme } from "antd";
import { THEME_ACCENT_HEX } from "./themeConfig.js";
import { useTheme } from "./useTheme.js";

/**
 * Bridges the SweaterCo theme system to Ant Design (used by the admin pages
 * and @ant-design/icons). The Black theme maps to Ant Design's dark algorithm;
 * every other colour theme is a light palette.
 */
export function AntdBridge({ children }) {
  const { theme, isDark } = useTheme();
  const colorPrimary = THEME_ACCENT_HEX[theme] || THEME_ACCENT_HEX.ocean;

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
