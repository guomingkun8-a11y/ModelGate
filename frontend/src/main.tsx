import '@ant-design/v5-patch-for-react-19'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { AuthProvider } from './stores/auth'
import './style.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: {
      colorPrimary: '#535dc9', colorSuccess: '#28724e', colorError: '#b33f37',
      colorText: '#302d3b', colorTextSecondary: '#625e6f', colorBorder: '#e1dce9',
      borderRadius: 8, fontSize: 13, controlHeight: 36,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif',
    } }}>
      <AntdApp><AuthProvider><App /></AuthProvider></AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
)
