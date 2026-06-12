import Badge from './Badge';
import BrandHomeButton from './BrandHomeButton';

export default function FlowTopbar({ trail, action, onHome }) {
  return (
    <header className="topbar flow-topbar">
      <div className="brand-zone">
        <BrandHomeButton onClick={onHome} />
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
