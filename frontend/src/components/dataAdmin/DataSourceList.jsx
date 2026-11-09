import { useEffect, useState } from "react";
import {
  Table, Tag, Button, Space, message, Descriptions, Drawer, Popconfirm,
  Dropdown, Pagination, Modal,
} from "antd";
import {
  ReloadOutlined, DeleteOutlined, EyeOutlined, DatabaseOutlined, MoreOutlined,
} from "@ant-design/icons";
import { getDataSources, deleteDataSource, getDataSourceData } from "../../services/dataAdminApi.js";

const PAGE_SIZE = 50;
const CARD_PAGE_SIZE = 10;

/** Small responsive helper: true when viewport is below the md breakpoint (768px). */
function useIsMobile(query = "(max-width: 767px)") {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  );
  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const mql = window.matchMedia(query);
    const onChange = (event) => setIsMobile(event.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return isMobile;
}

export default function DataSourceList() {
  const [dataSources, setDataSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [currentDataSource, setCurrentDataSource] = useState(null);
  const [dataPreview, setDataPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPage, setPreviewPage] = useState(1);
  const [cardPage, setCardPage] = useState(1);
  const [expandedId, setExpandedId] = useState(null);
  const isMobile = useIsMobile();
  // Defensive: never trust the API payload shape; a non-array here used to
  // crash the render (white screen). Keep a safe list for all consumers.
  const rows = Array.isArray(dataSources) ? dataSources : [];

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await getDataSources();
      const raw = res?.data;
      setDataSources(Array.isArray(raw) ? raw : []);
    } catch (error) {
      setDataSources([]);
      message.error("Failed to load data sources");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const loadPreview = async (record, page = 1) => {
    setPreviewLoading(true);
    try {
      const offset = (page - 1) * PAGE_SIZE;
      const res = await getDataSourceData(record.id, PAGE_SIZE, offset);
      setDataPreview(res.data);
      setPreviewPage(page);
    } catch (error) {
      message.error("Failed to load data");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleViewData = async (record) => {
    setCurrentDataSource(record);
    setDrawerVisible(true);
    setDataPreview(null);
    await loadPreview(record, 1);
  };

  const handleDelete = async (id) => {
    try {
      await deleteDataSource(id, false);
      message.success("Data source deactivated");
      fetchData();
    } catch (error) {
      message.error("Failed to delete");
    }
  };

  // Mobile: a menu item must not execute Deactivate directly — open the same
  // confirmation step (Modal.confirm) and run the unchanged API on confirm.
  const confirmDeactivate = (record) => {
    Modal.confirm({
      title: "Deactivate this data source?",
      content: "The SQLite table is kept. Only the catalog entry is marked inactive.",
      okText: "Yes",
      cancelText: "No",
      okButtonProps: { danger: true },
      onOk: () => handleDelete(record.id),
    });
  };

  const columns = [
    {
      title: "Source Name",
      dataIndex: "source_name",
      key: "source_name",
      width: 150,
      ellipsis: true,
      render: (text) => (
        <Space>
          <DatabaseOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: "Table Name",
      dataIndex: "table_name",
      key: "table_name",
      width: 110,
      render: (text) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: "Original File",
      dataIndex: "original_file",
      key: "original_file",
      width: 120,
      ellipsis: true,
    },
    {
      title: "Row Count",
      dataIndex: "row_count",
      key: "row_count",
      width: 90,
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      width: 140,
      ellipsis: true,
    },
    {
      title: "Status",
      key: "status",
      width: 90,
      render: (_, record) => (
        <Tag color={record.is_active ? "green" : "red"}>
          {record.is_active ? "Active" : "Inactive"}
        </Tag>
      ),
    },
    {
      title: "Created At",
      dataIndex: "created_at",
      key: "created_at",
      width: 100,
      ellipsis: true,
      render: (text) => (text ? new Date(text).toLocaleString() : ""),
    },
    {
      title: "Actions",
      key: "action",
      width: 200,
      fixed: "right",
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewData(record)}
          >
            View
          </Button>
          <Popconfirm
            title="Deactivate this data source?"
            description="The SQLite table is kept. Only the catalog entry is marked inactive."
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Deactivate
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const getPreviewColumns = () => {
    if (!dataPreview || !dataPreview.columns) return [];
    return dataPreview.columns
      .filter((col) => col.name && col.name !== "created_at")
      .map((col) => ({
        title: col.name,
        dataIndex: col.name,
        key: col.name,
        ellipsis: true,
        width: 120,
      }));
  };

  const renderMobileCards = () => {
    if (loading) {
      return <div className="py-10 text-center text-sm text-ink/50">Loading…</div>;
    }
    if (!rows.length) {
      return <div className="py-10 text-center text-sm text-ink/50">No data sources.</div>;
    }
    const start = (cardPage - 1) * CARD_PAGE_SIZE;
    const pageRows = rows.slice(start, start + CARD_PAGE_SIZE);
    return (
      <div className="space-y-3">
        {pageRows.map((record) => {
          const expanded = expandedId === record.id;
          return (
            <article key={record.id} className="rounded-xl border border-ink/10 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 truncate text-sm font-semibold text-ink">
                    <DatabaseOutlined /> <span className="truncate">{record.source_name}</span>
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Tag color="blue">{record.table_name}</Tag>
                    <Tag color={record.is_active ? "green" : "red"}>
                      {record.is_active ? "Active" : "Inactive"}
                    </Tag>
                    <span className="text-xs text-ink/55">{record.row_count} rows</span>
                  </div>
                </div>
                <Dropdown
                  trigger={["click"]}
                  menu={{
                    items: [
                      { key: "view", label: "View", icon: <EyeOutlined /> },
                      { key: "deactivate", label: "Deactivate", danger: true, icon: <DeleteOutlined /> },
                    ],
                    onClick: ({ key }) => {
                      if (key === "view") handleViewData(record);
                      else if (key === "deactivate") confirmDeactivate(record);
                    },
                  }}
                >
                  <button
                    type="button"
                    className="rounded-full border border-ink/10 p-2 text-ink/70 hover:border-brass"
                    aria-label={`More actions for ${record.source_name}`}
                  >
                    <MoreOutlined />
                  </button>
                </Dropdown>
              </div>

              <button
                type="button"
                onClick={() => setExpandedId(expanded ? null : record.id)}
                className="mt-3 text-xs font-medium text-accentText"
              >
                {expanded ? "Hide details" : "Show details"}
              </button>

              {expanded && (
                <dl className="mt-3 space-y-2 border-t border-ink/10 pt-3 text-xs">
                  <div>
                    <dt className="text-ink/50">Original file</dt>
                    <dd className="break-all text-ink/80">{record.original_file || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-ink/50">Description</dt>
                    <dd className="text-ink/80">{record.description || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-ink/50">Created at</dt>
                    <dd className="text-ink/80">
                      {record.created_at ? new Date(record.created_at).toLocaleString() : "—"}
                    </dd>
                  </div>
                </dl>
              )}
            </article>
          );
        })}
        {rows.length > CARD_PAGE_SIZE && (
          <div className="flex justify-center pt-2">
            <Pagination
              size="small"
              current={cardPage}
              pageSize={CARD_PAGE_SIZE}
              total={rows.length}
              showSizeChanger={false}
              onChange={(page) => setCardPage(page)}
            />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-w-0">
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16, gap: 12 }}>
        <h2 className="text-base font-semibold text-ink">Data Source Management</h2>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>Refresh</Button>
      </div>

      {isMobile ? (
        renderMobileCards()
      ) : (
        <div className="min-w-0 overflow-hidden">
          <Table
            columns={columns}
            dataSource={rows}
            loading={loading}
            rowKey="id"
            scroll={{ x: 1000 }}
            pagination={{ pageSize: 10 }}
          />
        </div>
      )}

      <Drawer
        title={`Data Preview - ${currentDataSource?.source_name || ""}`}
        placement="right"
        width={800}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {currentDataSource && (
          <Descriptions column={2} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Table Name">{currentDataSource.table_name}</Descriptions.Item>
            <Descriptions.Item label="Row Count">{currentDataSource.row_count}</Descriptions.Item>
            <Descriptions.Item label="Original File">{currentDataSource.original_file}</Descriptions.Item>
            <Descriptions.Item label="Description">{currentDataSource.description}</Descriptions.Item>
          </Descriptions>
        )}

        {previewLoading ? (
          <div style={{ textAlign: "center", padding: 40 }}>Loading...</div>
        ) : dataPreview && (
          <Table
            columns={getPreviewColumns()}
            dataSource={(dataPreview.data || []).map((row, i) => ({
              ...row,
              _rowKey: `${dataPreview.offset}-${i}`,
            }))}
            rowKey="_rowKey"
            scroll={{ x: "max-content" }}
            size="small"
            pagination={{
              current: previewPage,
              total: dataPreview.total,
              pageSize: PAGE_SIZE,
              showTotal: (total) => `Total ${total} rows`,
              onChange: (page) => {
                if (currentDataSource) {
                  loadPreview(currentDataSource, page);
                }
              },
            }}
          />
        )}
      </Drawer>
    </div>
  );
}
