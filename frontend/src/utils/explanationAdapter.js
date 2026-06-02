function createExplanationViewModel(response, suppliers = []) {
  const supplierByName = new Map(suppliers.map((supplier) => [supplier.name, supplier]));
  const supplierExplanations = (response?.supplier_explanations ?? []).map((item, index) => {
    const supplier = supplierByName.get(item.vendor_name) ?? suppliers[index] ?? {};

    return {
      cardSummary: item.card_summary ?? supplier.summary ?? "",
      checkRequired: item.check_required ?? [],
      logo: supplier.logo ?? getLogo(item.vendor_name, index),
      logoClass: supplier.logoClass ?? getLogoClass(index),
      quoteId: item.quote_id ?? supplier.id,
      rank: item.rank ?? supplier.rank ?? index + 1,
      strengths: formatList(item.strengths, supplier.strengths),
      vendorName: item.vendor_name ?? supplier.name ?? `공급사 ${index + 1}`,
      weaknesses: formatList(item.weaknesses, supplier.weakness),
    };
  });

  return {
    isFallback: Boolean(response?.warnings?.length),
    overallSummary: response?.overall_summary ?? "AI 근거 요약을 준비 중입니다.",
    provider: response?.provider ?? response?.metadata?.provider ?? "unknown",
    supplierExplanations,
    warnings: response?.warnings ?? [],
  };
}

function formatList(value, fallback = "-") {
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : fallback;
  return value || fallback;
}

function getLogo(name, index) {
  if (!name) return String(index + 1);
  return name.slice(0, 1).toUpperCase();
}

function getLogoClass(index) {
  return ["logo-blue", "logo-purple", "logo-teal", "logo-orange", "logo-gray"][index] ?? "logo-gray";
}

export { createExplanationViewModel };
