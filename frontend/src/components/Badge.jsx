export default function Badge({ children, tone = "blue" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
