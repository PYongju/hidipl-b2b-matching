-- hidipl-b2b-matching MariaDB init.sql
-- 기준: handover_20260529_v2 스키마 v1.4
-- 작성일: 2026-06-01

SET NAMES utf8mb4;
SET time_zone = '+09:00';

-- ------------------------------------
-- 프로젝트
-- ------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    project_id   VARCHAR(64)  NOT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id)
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
    quote_id                VARCHAR(128)   NOT NULL,             -- {vendor}_{datetime}_{hash8}
    project_id              VARCHAR(64)    NOT NULL,
    vendor_id               VARCHAR(64)             DEFAULT NULL,
    vendor_name             VARCHAR(256)   NOT NULL,
    received_at             DATETIME       NOT NULL,
    project_name            VARCHAR(256)   NOT NULL,
    total_supply_price      BIGINT         NOT NULL,             -- VAT 제외 공급가액
    total_with_vat          BIGINT                  DEFAULT NULL, -- VAT 포함 총액, Ranking 기준
    currency                VARCHAR(8)     NOT NULL DEFAULT 'KRW',
    delivery_weeks          INT                     DEFAULT NULL,
    delivery_basis_raw      VARCHAR(256)            DEFAULT NULL, -- 예: '계약 후 5주', '별도협의'
    warranty_months         INT                     DEFAULT NULL,
    notes_raw               TEXT                    DEFAULT NULL,
    extraction_confidence   DECIMAL(4,3)   NOT NULL DEFAULT 0.0, -- 0.0~1.0
    created_at              DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quote_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (vendor_id)  REFERENCES vendors(vendor_id)
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
    unit                    VARCHAR(32)    NOT NULL,             -- EA, SET 등
    unit_price              BIGINT                  DEFAULT NULL,
    total_price             BIGINT                  DEFAULT NULL,
    is_optional             TINYINT(1)     NOT NULL DEFAULT 0,
    spec_raw                TEXT                    DEFAULT NULL,
    spec_parsed             JSON                    DEFAULT NULL,
    extraction_confidence   DECIMAL(4,3)   NOT NULL DEFAULT 0.0,
    PRIMARY KEY (id),
    FOREIGN KEY (quote_id) REFERENCES quotes(quote_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------
-- 매칭 결과 (MatchResult 기준)
-- ------------------------------------
CREATE TABLE IF NOT EXISTS match_results (
    match_id            VARCHAR(64)    NOT NULL,
    project_id          VARCHAR(64)    NOT NULL,
    created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (match_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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
    FOREIGN KEY (match_id) REFERENCES match_results(match_id),
    FOREIGN KEY (quote_id) REFERENCES quotes(quote_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;