import Badge from './Badge';

export default function FlowTopbar({ trail, action }) {
  return (
    <header className="topbar flow-topbar">
      <div className="brand-zone">
        <div className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="brand-title">견적 검토 쿼파일럿</div>
        <Badge tone="gray">v1.3.2</Badge>
        {trail && (
          <>
            <div className="top-divider" />
            <span className="breadcrumb-muted">{trail}</span>
          </>
        )}
      </div>
      <div className="user-zone">{action}</div>
    </header>
  );
}
