-- hidipl-b2b-matching MariaDB init.sql
-- 기준: handover_20260529_v2 스키마 v1.7
-- 작성일: 2026-06-01
-- 갱신일: 2026-06-14

SET NAMES utf8mb4;
SET time_zone = '+09:00';

-- ------------------------------------
-- 사용자 (Azure Entra ID 연동)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id         VARCHAR(64)             NOT NULL,
    email           VARCHAR(256)            NOT NULL,
    display_name    VARCHAR(256)            DEFAULT NULL,
    user_name       VARCHAR(256)            DEFAULT NULL,
    role            ENUM('admin','member')  NOT NULL DEFAULT 'member',
    is_active       TINYINT(1)              NOT NULL DEFAULT 1,
    last_login_at   DATETIME                DEFAULT NULL,
    created_at      DATETIME                NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------
-- 프로젝트
-- ------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    project_id              VARCHAR(64)   NOT NULL,
    created_by              VARCHAR(64)   DEFAULT NULL,            -- users.user_id (Entra ID 연동 전 NULL 허용)
    internal_notes          JSON          DEFAULT NULL,
    created_at              DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status                  VARCHAR(32)   NOT NULL DEFAULT 'created',
    workflow_status         VARCHAR(32)   DEFAULT NULL,              -- 견적 수집/매칭 진행 상황 (예: 'quotes_collected', 'matching_completed')
    company_name            VARCHAR(256)  DEFAULT NULL,
    location                VARCHAR(256)  DEFAULT NULL,
    deadline                VARCHAR(64)   DEFAULT NULL,
    request_text            TEXT          DEFAULT NULL,
    requirement_result_json JSON          NULL,                    -- RequirementIngestionResult 직렬화 (6/14 추가)
    PRIMARY KEY (project_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------
-- 파트너사 (VendorSnapshot 기준)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id              VARCHAR(64)    NOT NULL,
    vendor_name            VARCHAR(256)   NOT NULL,
    is_premium_partner     TINYINT(1)     NOT NULL DEFAULT 0,
    past_success_rate      DECIMAL(5,4)            DEFAULT NULL,  -- 0.0~1.0
    response_speed_score   DECIMAL(5,4)            DEFAULT NULL,  -- 0.0~1.0
    CONSTRAINT chk_past_success_rate    CHECK (past_success_rate   IS NULL OR (past_success_rate   >= 0.0 AND past_success_rate   <= 1.0)),
    CONSTRAINT chk_response_speed_score CHECK (response_speed_score IS NULL OR (response_speed_score >= 0.0 AND response_speed_score <= 1.0)),
    response_speed         VARCHAR(16)             DEFAULT NULL,  -- 빠름|보통|느림
    financial_status       VARCHAR(16)             DEFAULT NULL,  -- 양호|보통|주의
    is_excluded            TINYINT(1)     NOT NULL DEFAULT 0,
    specialty_tags         JSON                    DEFAULT NULL,  -- list[str]
    source                 VARCHAR(256)   NOT NULL DEFAULT 'data/partners.py',
    PRIMARY KEY (vendor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------
-- 견적서 (QuoteDocument 기준)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS quotes (
    quote_id                VARCHAR(128)   NOT NULL,              -- {vendor}_{datetime}_{hash8}
    project_id              VARCHAR(64)    NOT NULL,
    vendor_id               VARCHAR(64)             DEFAULT NULL,
    vendor_name             VARCHAR(256)   NOT NULL,
    received_at             DATETIME       NOT NULL,
    project_name            VARCHAR(256)   NOT NULL,
    total_supply_price      BIGINT         NOT NULL,              -- VAT 제외 공급가액
    total_with_vat          BIGINT                  DEFAULT NULL, -- VAT 포함 총액, Ranking 기준
    currency                VARCHAR(8)     NOT NULL DEFAULT 'KRW',
    delivery_weeks          INT                     DEFAULT NULL,
    delivery_basis_raw      VARCHAR(256)            DEFAULT NULL, -- 예: '계약 후 5주', '별도협의'
    warranty_months         INT                     DEFAULT NULL,
    notes_raw               TEXT                    DEFAULT NULL,
    extraction_confidence   DECIMAL(4,3)   NOT NULL DEFAULT 0.0, -- 0.0~1.0
    created_by              VARCHAR(64)             DEFAULT NULL, -- users.user_id (Entra ID 연동 전 NULL 허용)
    created_at              DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quote_id),
    CONSTRAINT chk_quotes_extraction_confidence CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    FOREIGN KEY (vendor_id)  REFERENCES vendors(vendor_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------
-- 견적 품목 (LineItem 기준)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS line_items (
    id                      BIGINT         NOT NULL AUTO_INCREMENT,
    quote_id                VARCHAR(128)   NOT NULL,
    name                    VARCHAR(256)   NOT NULL,
    category                ENUM(
                                'DISPLAY','MOUNT','PLAYER',
                                'CABLE','INSTALL','SOFTWARE','ETC'
                            )              NOT NULL,
    quantity                DECIMAL(10,3)  NOT NULL,
    unit                    VARCHAR(32)    NOT NULL,              -- EA, SET 등
    unit_price              BIGINT                  DEFAULT NULL,
    total_price             BIGINT                  DEFAULT NULL,
    is_optional             TINYINT(1)     NOT NULL DEFAULT 0,
    spec_raw                TEXT                    DEFAULT NULL,
    spec_parsed             JSON                    DEFAULT NULL,
    extraction_confidence   DECIMAL(4,3)   NOT NULL DEFAULT 0.0,
    PRIMARY KEY (id),
    CONSTRAINT chk_line_items_extraction_confidence CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0),
    FOREIGN KEY (quote_id) REFERENCES quotes(quote_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------
-- 견적 풀 (QuotePoolRecord 기준)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS quote_pools (
    quote_pool_id               VARCHAR(64)    NOT NULL,
    project_id                  VARCHAR(64)    NOT NULL,
    uploaded_files_json         JSON           NULL,
    quote_ingestion_results_json JSON          NOT NULL,           -- QuoteIngestionResult 목록 직렬화
    failed_files_json           JSON           NULL,
    created_at                  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quote_pool_id),
    CONSTRAINT `quote_pools_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IF NOT EXISTS idx_quote_pools_project_id ON quote_pools(project_id);

-- ------------------------------------
-- 매칭 결과 (MatchResult 기준)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS match_results (
    match_id                    VARCHAR(64)    NOT NULL,
    project_id                  VARCHAR(64)    NOT NULL,
    created_by                  VARCHAR(64)             DEFAULT NULL, -- users.user_id (Entra ID 연동 전 NULL 허용)
    created_at                  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recommendation_result_json  JSON           NULL,                  -- RecommendationPipelineResult 직렬화 (6/14 추가)
    explanation_result_json     JSON           NULL,                  -- RecommendationExplanationResult 직렬화 (6/14 추가)
    PRIMARY KEY (match_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IF NOT EXISTS idx_match_results_project_id_created_at ON match_results(project_id, created_at);

CREATE TABLE IF NOT EXISTS match_result_items (
    id                  BIGINT         NOT NULL AUTO_INCREMENT,
    match_id            VARCHAR(64)    NOT NULL,
    quote_id            VARCHAR(128)   NOT NULL,
    rank                INT            NOT NULL,
    final_score         DECIMAL(5,2)   NOT NULL,                -- 0.0~100.0
    spec_score          DECIMAL(5,2)   NOT NULL DEFAULT 0.0,
    price_score         DECIMAL(5,2)   NOT NULL DEFAULT 0.0,
    delivery_score      DECIMAL(5,2)   NOT NULL DEFAULT 0.0,
    warranty_score      DECIMAL(5,2)   NOT NULL DEFAULT 0.0,
    installation_score  DECIMAL(5,2)   NOT NULL DEFAULT 0.0,
    matched_rules       JSON                    DEFAULT NULL,   -- list[str]
    filter_reasons      JSON                    DEFAULT NULL,   -- list[str], 비면 통과
    check_required      JSON                    DEFAULT NULL,   -- list[str]
    rule_warnings       JSON                    DEFAULT NULL,   -- list[str]
    PRIMARY KEY (id),
    UNIQUE KEY uq_match_rank (match_id, rank),
    CONSTRAINT chk_final_score        CHECK (final_score        >= 0.0 AND final_score        <= 100.0),
    CONSTRAINT chk_spec_score         CHECK (spec_score         >= 0.0 AND spec_score         <= 100.0),
    CONSTRAINT chk_price_score        CHECK (price_score        >= 0.0 AND price_score        <= 100.0),
    CONSTRAINT chk_delivery_score     CHECK (delivery_score     >= 0.0 AND delivery_score     <= 100.0),
    CONSTRAINT chk_warranty_score     CHECK (warranty_score     >= 0.0 AND warranty_score     <= 100.0),
    CONSTRAINT chk_installation_score CHECK (installation_score >= 0.0 AND installation_score <= 100.0),
    FOREIGN KEY (match_id) REFERENCES match_results(match_id) ON DELETE CASCADE,
    FOREIGN KEY (quote_id) REFERENCES quotes(quote_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------
-- 파트너 후보 (CandidateVendorRecord 기준)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS candidate_vendors (
    candidate_vendor_id         VARCHAR(64)    NOT NULL,
    project_id                  VARCHAR(64)    NOT NULL,
    requirement_result_json     JSON           NULL,                  -- RequirementIngestionResult 직렬화
    requested_vendor_ids_json   JSON           NULL,                  -- list[str]
    candidate_vendor_result_json JSON          NOT NULL,              -- PartnerMatchingResult 직렬화
    selected_vendor_names_json  JSON           NULL,                  -- list[str]
    requested_vendor_names_json JSON           NULL,                  -- list[str]
    top_n                       INT            NULL,
    similarity_threshold        FLOAT          NULL,
    executed_at                 DATETIME       NULL,
    created_at                  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (candidate_vendor_id),
    CONSTRAINT `candidate_vendors_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IF NOT EXISTS idx_candidate_vendors_project_id ON candidate_vendors(project_id);