"""事实表模型（docs/03 §2.1）。

约定：时间一律 INTEGER epoch_ms（UTC）；金额 REAL；JSON 数组/对象存 TEXT(JSON)；
清洗三列原则：规范列 + *_raw 原始列并存，禁止原地覆盖丢原文。
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class TimestampMixin:
    """本地审计时间戳（epoch_ms）。"""

    created_at: Mapped[int] = mapped_column(BigInteger, default=_now_ms, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=_now_ms, onupdate=_now_ms, nullable=False)


class RawCase(Base):
    """原始值快照表（实现计划「双表架构」之一）。

    同步时把飞书记录的原始 fields 整包留档（含 35 字段未清洗原值），
    详情页「原始视图」（GET /cases/{id}/raw）与清洗回放均由此出。
    """

    __tablename__ = "raw_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    table_name: Mapped[str] = mapped_column(String(32), default="cases", nullable=False)  # cases / songs
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)  # 飞书 fields 原样 JSON
    synced_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Case(Base, TimestampMixin):
    """案件主表（对应飞书 35 字段；docs/03 §2.1 列定义）。"""

    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("record_id", name="uq_cases_record_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)  # 同步幂等键
    # ① 案号（清洗）/ 原始 / 合并拆分
    case_no: Mapped[str | None] = mapped_column(String(255), index=True)
    case_no_raw: Mapped[str | None] = mapped_column(Text)
    case_no_ext: Mapped[list | None] = mapped_column(Text)  # JSON 数组：按合并案件数拆出的案号
    related_case_no: Mapped[str | None] = mapped_column(String(255))
    # ③ 案件状态 / ④ 最近开庭
    case_status: Mapped[str | None] = mapped_column(String(64), index=True)
    court_date: Mapped[int | None] = mapped_column(BigInteger)
    # ⑤ 合并案件数 / ⑥ 收案年份（unknown=-1）/ 原始
    merged_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    year_raw: Mapped[str | None] = mapped_column(String(64))
    accept_date: Mapped[int | None] = mapped_column(BigInteger)  # ⑦ 收案时间（与 year 交叉校验）
    # ⑧⑨ 原告 / 被告（公司名归一）+ 原始留痕
    plaintiff: Mapped[str | None] = mapped_column(String(255), index=True)
    plaintiff_raw: Mapped[str | None] = mapped_column(Text)
    defendant: Mapped[list | None] = mapped_column(Text)  # JSON 数组（规范名）
    defendant_raw: Mapped[list | None] = mapped_column(Text)  # JSON 数组（原始）
    other_parties: Mapped[str | None] = mapped_column(Text)  # ⑩
    # ⑪ 案由 / ⑫ 法院（剔除仲裁机构后的规范数组）/ 仲裁机构（derived）/ 原始
    cause: Mapped[str | None] = mapped_column(String(128), index=True)
    court: Mapped[list | None] = mapped_column(Text)
    arbitration_org: Mapped[list | None] = mapped_column(Text)
    court_raw: Mapped[str | None] = mapped_column(Text)
    # ⑬ 标的 / ⑭ 涉案歌曲数量（公式值本地复刻） / ⑮ 艺人透传
    amount: Mapped[float | None] = mapped_column(Float)
    song_count: Mapped[int | None] = mapped_column(Integer)
    artist: Mapped[list | None] = mapped_column(Text)
    # ⑯ 单曲判赔（分母 0 → NULL）
    per_song_amount: Mapped[float | None] = mapped_column(Float)
    # ⑰⑱ 一审/二审文书时间
    doc1_date: Mapped[int | None] = mapped_column(BigInteger)
    doc2_date: Mapped[int | None] = mapped_column(BigInteger)
    # ⑲⑳ 结案原因（胜负判定源）/ 具体结案原因
    resolve: Mapped[str | None] = mapped_column(String(64), index=True)
    resolve_detail: Mapped[str | None] = mapped_column(Text)
    # ㉑ 支付主体 / ㉒ 对方诉求支持率（公式值 0~1，除零→NULL）
    payer: Mapped[str | None] = mapped_column(String(32), index=True)
    support_rate: Mapped[float | None] = mapped_column(Float)
    # ㉓ 支付时间 / ㉔ 支付总金额（混合口径）
    pay_date: Mapped[int | None] = mapped_column(BigInteger)
    pay_amount: Mapped[float | None] = mapped_column(Float)
    # ㉕ 案件负责人（user_id + 姓名缓存）
    case_owner: Mapped[str | None] = mapped_column(String(64))
    case_owner_name: Mapped[str | None] = mapped_column(String(64))
    # ㉖ 律师代理费（错配枚举留档；derived 推断见 R09，Phase 0 暂不启用）
    lawyer_fee: Mapped[str | None] = mapped_column(String(128))
    # ㉗ 办案笔记（FTS 索引）
    notes: Mapped[str | None] = mapped_column(Text)
    # ㉘ 结案日期 / ㉛ 执行案号 / ㉜ 承办法官及联系方式 / judge_name derived
    close_date: Mapped[int | None] = mapped_column(BigInteger)
    exec_case_no: Mapped[str | None] = mapped_column(String(255))
    judge_info: Mapped[str | None] = mapped_column(Text)
    judge_name: Mapped[str | None] = mapped_column(String(64))
    # ㉞ 业务线（8 枚举）
    biz_line: Mapped[str | None] = mapped_column(String(64), index=True)
    # ㉟ 父记录 SingleLink（系列案树；自关联 record_id）
    parent_record_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # ㉚ 备注 / ㉝ 撤卷申请人
    remark: Mapped[str | None] = mapped_column(Text)
    withdraw_user: Mapped[str | None] = mapped_column(String(64))
    # 同步元数据 / 清洗产出
    synced_at: Mapped[int | None] = mapped_column(BigInteger)
    dirty_flags: Mapped[list | None] = mapped_column(Text)  # JSON：[命中规则 id 列表]
    hash: Mapped[str | None] = mapped_column(String(64))  # 全字段序列化哈希（增量比对）

    # 关联（多对多 song_case）
    songs: Mapped[list["SongCase"]] = relationship(back_populates="case", cascade="all, delete-orphan")  # noqa: F821


class Song(Base, TimestampMixin):
    """涉及歌曲清单（飞书 tblCGACAzAMGd5eX）。"""

    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    song_name: Mapped[str | None] = mapped_column(String(255), index=True)  # 归一：去版本后缀
    song_name_raw: Mapped[str | None] = mapped_column(Text)
    artist: Mapped[str | None] = mapped_column(String(255))
    synced_at: Mapped[int | None] = mapped_column(BigInteger)

    cases: Mapped[list["SongCase"]] = relationship(back_populates="song")  # noqa: F821


class SongCase(Base):
    """歌曲↔案件多对多（DuplexLink 展开产物）。"""

    __tablename__ = "song_case"
    __table_args__ = (UniqueConstraint("song_id", "case_id", name="uq_song_case"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True, nullable=False)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True, nullable=False)
    role: Mapped[str | None] = mapped_column(String(16))  # 主 / 关联（composer/member 解析）

    song: Mapped["Song"] = relationship(back_populates="cases")  # noqa: F821
    case: Mapped["Case"] = relationship(back_populates="songs")  # noqa: F821