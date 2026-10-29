import { Alert, Button, Skeleton } from 'antd'

export default function PageFeedback({loading, error, onRetry}: {loading: boolean; error: string; onRetry: () => void}) {
  if (error) return <Alert type="error" showIcon message="数据加载失败" description={error} action={<Button size="small" onClick={onRetry}>重新加载</Button>} />
  if (loading) return <Skeleton active paragraph={{rows: 7}} />
  return null
}
