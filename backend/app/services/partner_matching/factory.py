from services.config import get_settings
from services.embedding.factory import create_embedding_provider
from services.partner_matching.partner_matching_pipeline import PartnerMatchingPipeline
from services.ranking.partner_loader import load_partner_profiles
from services.similarity.factory import create_similarity_provider


def create_partner_matching_pipeline(settings=None) -> PartnerMatchingPipeline:
    if settings is None:
        settings = get_settings()

    embedding_provider = create_embedding_provider("azure_openai")
    similarity_provider = create_similarity_provider("cosine")
    partner_profiles = load_partner_profiles()

    return PartnerMatchingPipeline(
        embedding_provider=embedding_provider,
        similarity_provider=similarity_provider,
        partner_profiles=partner_profiles,
    )
