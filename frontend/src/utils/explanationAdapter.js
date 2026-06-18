const MAX_EXPLANATION_SUPPLIERS = 3;

function isExplicitFallbackWarning(warning) {
  const text = String(warning ?? "");
  return (
    /llm/i.test(text) && /fail|fallback|template/i.test(text) ||
    /template fallback used/i.test(text) ||
    /azure openai explanation generation failed/i.test(text) ||
    /fallback/i.test(text)
  );
}

function isExplanationFallback(response) {
  const provider = response?.provider ?? "";

  if (provider === "template" || provider.endsWith("_fallback_template")) {
    return true;
  }

  return (response?.warnings ?? []).some(isExplicitFallbackWarning);
}

function createExplanationViewModel(response, suppliers = []) {
  const supplierByName = new Map(
    suppliers.map((supplier) => [supplier.name, supplier]),
  );

  const supplierExplanations = (response?.supplier_explanations ?? [])
    .slice(0, MAX_EXPLANATION_SUPPLIERS)
    .map((item, index) => {
      const supplier =
        supplierByName.get(item.vendor_name) ?? suppliers[index] ?? {};

      return {
        cardSummary: item.card_summary ?? "",
        checkRequired: item.check_required ?? [],
        logo: supplier.logo ?? getLogo(item.vendor_name, index),
        logoClass: supplier.logoClass ?? getLogoClass(index),
        quoteId: item.quote_id ?? supplier.id,
        rank: item.rank ?? supplier.rank ?? index + 1,
        strengthItems: ensureArray(item.strengths, supplier.strengths),
        strengths: formatList(item.strengths, supplier.strengths),
        vendorName:
          item.vendor_name ?? supplier.name ?? `공급사 ${index + 1}`,
        weaknessItems: ensureArray(
          item.weaknesses,
          supplier.weakness ?? "특이 약점 없음",
        ),
        weaknesses: formatList(
          item.weaknesses,
          supplier.weakness ?? "특이 약점 없음",
        ),
      };
    });

  return {
    isFallback: isExplanationFallback(response),
    overallSummary:
      response?.overall_summary ?? "AI 근거 요약을 준비하고 있어요.",
    provider: response?.provider ?? response?.metadata?.provider ?? "unknown",
    supplierExplanations,
    warnings: response?.warnings ?? [],
  };
}

function formatList(value, fallback = "-") {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(", ") : fallback;
  }
  return value || fallback;
}

function ensureArray(value, fallback = "-") {
  if (Array.isArray(value)) return value.filter(Boolean);

  if (typeof value === "string" && value.trim()) {
    return value
      .split(/,\s+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  if (typeof fallback === "string" && fallback.trim()) {
    return [fallback.trim()];
  }

  return [];
}

function getLogo(name, index) {
  if (!name) return String(index + 1);
  return name.slice(0, 1).toUpperCase();
}

function getLogoClass(index) {
  return (
    ["logo-blue", "logo-purple", "logo-teal", "logo-orange", "logo-gray"][
      index
    ] ?? "logo-gray"
  );
}

export { createExplanationViewModel, isExplanationFallback };
