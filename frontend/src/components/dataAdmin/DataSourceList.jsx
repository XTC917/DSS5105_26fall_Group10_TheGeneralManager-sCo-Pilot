import { useEffect, useState } from "react";
import {
  Table, Tag, Button, Space, message, Descriptions, Drawer, Popconfirm,
  Dropdown, Pagination, Modal, Form, Input,
} from "antd";
import {
  ReloadOutlined, DeleteOutlined, EyeOutlined, DatabaseOutlined, MoreOutlined,
  EditOutlined, SaveOutlined,
} from "@ant-design/icons";
import {
  getDataSources, deleteDataSource, getDataSourceData, updateDataSourceRows,
} from "../../services/dataAdminApi.js";

const PAGE_SIZE = 50;
const CARD_PAGE_SIZE = 10;

// Must mirror backend/services/data_admin_updates.py. The backend is the source
// of truth and will reject anything else; these maps only drive the UI so the
// form disables protected columns and normalises empty strings to null.
const PRIMARY_KEYS = {
  orders: ["order_id"],
  production_log: ["production_date", "stage"],
  workshops: ["workshop_id", "makes"],
};
const NULLABLE_COLUMNS = {
  orders: ["completed_date", "days_late"],
  production_log: [],
  workshops: ["max_batch_pieces"],
};
const MAX_BATCH = 50;

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

function rowKeyObject(primaryKeys, row) {
  return Object.fromEntries(primaryKeys.map((column) => [column, row[column]]));
}

function rowKeyText(object) {
  return JSON.stringify(object);
}

function summarizeChanges(pendingUpdates) {
  const columns = new Set();
  pendingUpdates.forEach((item) => Object.keys(item.changes).forEach((c) => columns.add(c)));
  return { rows: pendingUpdates.length, columns: [...columns] };
}

export default function DataSourceList() {
  const [dataSources, setDataSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [currentDataSource, setCurrentDataSource] = useState(null);
  const [dataPreview, setDataPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPage, setPreviewPage] = useState(1);
  const [cardPage, setCardPage] = useState(1);
  const [expandedId, setExpandedId] = useState(null);
  const [editRow, setEditRow] = useState(null);
  const [editVisible, setEditVisible] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState([]);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const isMobile = useIsMobile();
  // Defensive: never trust the API payload shape; a non-array here used to
  // crash the render (white screen). Keep a safe list for all consumers.
  const rows = Array.isArray(dataSources) ? dataSources : [];
  const primaryKeys = PRIMARY_KEYS[currentDataSource?.table_name] || [];

  const fetchData = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const res = await getDataSources();
      const raw = res?.data;
      setDataSources(Array.isArray(raw) ? raw : []);
    } catch (error) {
      setDataSources([]);
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail || error?.message || "Failed to load data sources";
      const text = typeof detail === "string" ? detail : JSON.stringify(detail);
      setLoadError(status ? `HTTP ${status}: ${text}` : text);
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
    setPendingUpdates([]);
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

  // ---- Row editing (Edit -> Stage -> Clear -> Save batch) ------------------

  function stagedFor(row) {
    if (!row) return null;
    const marker = rowKeyText(rowKeyObject(primaryKeys, row));
    return pendingUpdates.find(
      (item) => rowKeyText(item.key) === marker,
    );
  }

  const openEditor = (row) => {
    const staged = stagedFor(row);
    setEditRow(row);
    form.setFieldsValue({
      ...row,
      ...(staged?.changes || {}),
    });
    setEditVisible(true);
  };

  const closeEditor = () => {
    setEditVisible(false);
    setEditRow(null);
  };

  const stageUpdate = async () => {
    if (!currentDataSource || !editRow) return;
    let values;
    try {
      values = await form.validateFields();
    } catch {
      return; // validation errors surface inside the form
    }
    const nullable = NULLABLE_COLUMNS[currentDataSource.table_name] || [];
    const changes = {};
    Object.entries(values).forEach(([column, value]) => {
      if (primaryKeys.includes(column)) return;
      const normalized = value === "" && nullable.includes(column) ? null : value;
      if (String(normalized ?? "") !== String(editRow[column] ?? "")) {
        changes[column] = normalized;
      }
    });
    if (Object.keys(changes).length === 0) {
      message.info("No changed fields to stage");
      return;
    }
    const marker = rowKeyText(rowKeyObject(primaryKeys, editRow));
    const exists = pendingUpdates.some((item) => rowKeyText(item.key) === marker);
    if (!exists && pendingUpdates.length >= MAX_BATCH) {
      message.error(`A batch can contain at most ${MAX_BATCH} rows`);
      return;
    }
    const update = { key: rowKeyObject(primaryKeys, editRow), changes };
    setPendingUpdates((current) => [
      ...current.filter((item) => rowKeyText(item.key) !== marker),
      update,
    ]);
    closeEditor();
    message.success("Row change staged. Save the batch to apply it.");
  };

  const clearPending = () => {
    if (pendingUpdates.length === 0 || saving) return;
    if (pendingUpdates.length === 1) {
      setPendingUpdates([]);
      message.info("Cleared the staged change.");
      return;
    }
    Modal.confirm({
      title: "Clear all staged changes?",
      content: `This discards staged changes for ${pendingUpdates.length} rows and restores the original values. Nothing is written to the database.`,
      okText: "Clear all",
      cancelText: "Keep",
      okButtonProps: { danger: true },
      onOk: () => {
        setPendingUpdates([]);
        message.info("Cleared all staged changes.");
      },
    });
  };

  const savePending = async () => {
    if (!currentDataSource || pendingUpdates.length === 0 || saving) return;
    setSaving(true);
    try {
      const response = await updateDataSourceRows(currentDataSource.id, pendingUpdates);
      const count = response?.data?.updated_count ?? pendingUpdates.length;
      message.success(`${count} row(s) updated atomically`);
      setPendingUpdates([]);
      await loadPreview(currentDataSource, previewPage);
      await fetchData();
    } catch (error) {
      // Keep the staged changes so the admin can fix and retry. The backend
      // rolls back the whole batch on any error, so nothing was partially saved.
      const detail = error?.response?.data?.detail || "Failed to update rows";
      const text = typeof detail === "string" ? detail : JSON.stringify(detail);
      Modal.error({
        title: "Batch save failed",
        content: `${text}. No rows were changed (the batch is applied atomically). Your staged edits are kept.`,
      });
    } finally {
      setSaving(false);
    }
  };

  const confirmSave = () => {
    if (pendingUpdates.length === 0 || saving) return;
    const { rows: rowCount, columns } = summarizeChanges(pendingUpdates);
    Modal.confirm({
      title: "Save staged changes?",
      content: (
        <div className="space-y-1 text-sm">
          <p>
            You are about to update <b>{rowCount}</b> row(s) in <b>{currentDataSource?.table_name}</b>.
          </p>
          <p className="text-ink/60">Fields: {columns.join(", ") || "—"}</p>
          <p className="text-ink/60">
            The batch is applied in one transaction — if any row fails, nothing is saved.
          </p>
        </div>
      ),
      okText: "Save batch",
      cancelText: "Cancel",
      onOk: savePending,
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
    const cols = dataPreview.columns
      .filter((col) => col.name && col.name !== "created_at")
      .map((col) => ({
        title: col.name,
        dataIndex: col.name,
        key: col.name,
        ellipsis: true,
        width: 130,
      }));
    cols.push({
      title: "Actions",
      key: "_actions",
      fixed: "right",
      width: 110,
      render: (_, row) => {
        const staged = stagedFor(row);
        return (
          <Space size={4}>
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEditor(row)}
            >
              Edit
            </Button>
            {staged && <Tag color="gold">Staged</Tag>}
          </Space>
        );
      },
    });
    return cols;
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

  const previewColumns = dataPreview?.columns?.filter(
    (col) => col.name && col.name !== "created_at",
  ) || [];

  return (
    <div className="min-w-0">
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16, gap: 12 }}>
        <h2 className="text-base font-semibold text-ink">Data Source Management</h2>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>Refresh</Button>
      </div>

      {loadError && (
        <div className="mb-3 rounded-card border border-danger/30 bg-dangerSoft px-3 py-2 text-sm text-danger" role="alert">
          Failed to load data sources — {loadError}
          <Button size="small" className="ml-2" onClick={fetchData}>Retry</Button>
        </div>
      )}

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
        width={isMobile ? "100%" : 800}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        styles={{ body: { paddingBottom: "max(16px, env(safe-area-inset-bottom))" } }}
      >
        {currentDataSource && (
          <Descriptions column={isMobile ? 1 : 2} size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Table Name">{currentDataSource.table_name}</Descriptions.Item>
            <Descriptions.Item label="Row Count">{currentDataSource.row_count}</Descriptions.Item>
            <Descriptions.Item label="Original File">{currentDataSource.original_file}</Descriptions.Item>
            <Descriptions.Item label="Description">{currentDataSource.description}</Descriptions.Item>
          </Descriptions>
        )}

        {previewLoading ? (
          <div style={{ textAlign: "center", padding: 40 }}>Loading...</div>
        ) : dataPreview && (
          <>
            <div
              className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-card border border-line bg-surfaceMuted/60 px-3 py-2"
              role="status"
            >
              <span className="text-xs text-ink/70">
                {pendingUpdates.length} pending row change(s). Edits are staged locally; Save applies the
                whole batch in one database transaction.
              </span>
              <Space>
                <Button
                  size="small"
                  onClick={clearPending}
                  disabled={pendingUpdates.length === 0 || saving}
                >
                  Clear
                </Button>
                <Button
                  size="small"
                  type="primary"
                  icon={<SaveOutlined />}
                  loading={saving}
                  disabled={pendingUpdates.length === 0 || saving}
                  onClick={confirmSave}
                >
                  Save batch
                </Button>
              </Space>
            </div>
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
          </>
        )}
      </Drawer>

      <Modal
        title="Stage row changes"
        open={editVisible}
        onOk={stageUpdate}
        onCancel={closeEditor}
        okText="Stage change"
        destroyOnClose
        forceRender
        styles={{ body: { maxHeight: "80dvh", overflowY: "auto", paddingBottom: "max(8px, env(safe-area-inset-bottom))" } }}
      >
        <p className="mb-3 text-xs text-ink/60">
          Primary-key columns are read-only. Empty values become NULL only for nullable columns. Nothing is
          written until you Save the batch.
        </p>
        <Form form={form} layout="vertical" preserve={false}>
          {previewColumns.map((column) => {
            const isKey = primaryKeys.includes(column.name);
            return (
              <Form.Item
                key={column.name}
                name={column.name}
                label={(
                  <span className="flex items-center gap-2">
                    {column.name}
                    {isKey && <Tag color="default">key</Tag>}
                  </span>
                )}
              >
                <Input disabled={isKey} autoComplete="off" />
                <div className="mt-1 truncate text-[11px] text-ink/45">
                  Original: {editRow?.[column.name] == null ? "NULL" : String(editRow[column.name])}
                </div>
              </Form.Item>
            );
          })}
        </Form>
      </Modal>
    </div>
  );
}
