const labels: Record<string, string> = {
  success: '成功', error: '失败', running: '处理中', healthy: '运行正常',
  disabled: '已停用', active: '使用中', revoked: '已撤销',
}
export default function StatusTag({ status }: { status: string }) {
  return <span className={`status-tag ${status}`}><span className="status-dot" />{labels[status] || status}</span>
}
