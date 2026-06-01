import Badge from './Badge';

export default function TableCell({ supplier, rowIndex }) {
  const value =
    typeof rowIndex === "number" ? supplier.quote[rowIndex] : supplier.comparison[rowIndex];
  const isBest = supplier.id === "b" && rowIndex === "quoteAmount";
  const needsCheck = supplier.id === "c" && rowIndex === "installationCost";
  const missing = !value;
  const specWarn = supplier.id === "c" && rowIndex === 0;

  if (missing) return <Badge tone="gray">미기재</Badge>;

  return (
    <div className="table-cell-content">
      {isBest ? (
        <span className="price-best">{value}</span>
      ) : specWarn ? (
        <span>
          55인치, 4K UHD, <b className="orange">450nit</b>, 24/7
        </span>
      ) : (
        <span>{value}</span>
      )}
      {isBest && <Badge tone="green">최저가</Badge>}
      {needsCheck && <Badge tone="orange">확인 필요</Badge>}
    </div>
  );
}
