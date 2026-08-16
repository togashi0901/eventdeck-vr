// 03_API仕様書と一致させるAPI型定義 (M1 範囲)

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: { field: string; reason: string }[];
  };
}

export interface MessageResponse {
  message: string;
}

export interface MeOrganization {
  id: string;
  name: string;
  role: "owner" | "member";
}

export interface MeResponse {
  id: string;
  email: string;
  has_profile: boolean;
  organizations: MeOrganization[];
}

export type Platform =
  | "pcvr"
  | "desktop"
  | "quest_standalone"
  | "mobile"
  | "unknown";

export interface Profile {
  display_name: string;
  vrchat_username: string | null;
  platform: Platform;
  device_note: string | null;
  x_account: string | null;
  discord_account: string | null;
  bio: string | null;
}

// --- M2: 団体・イベント ---

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  website_url: string | null;
  plan: string;
  created_at: string;
}

export interface Member {
  user_id: string;
  email: string;
  display_name: string | null;
  role: "owner" | "member";
  joined_at: string;
}

export type EventPlatform =
  | "vrchat"
  | "cluster"
  | "resonite"
  | "real"
  | "other";
export type SelectionMethod = "lottery" | "first_come";
export type EventStatus =
  | "draft"
  | "published"
  | "closed"
  | "finished"
  | "canceled";
export type Visibility = "public" | "unlisted";

export interface ApplicationState {
  applied: boolean;
  status: string | null;
}

export interface EventData {
  id: string;
  organization: { id: string; name: string; slug: string };
  title: string;
  description: string;
  platform: EventPlatform;
  world_name: string | null;
  world_url: string | null;
  starts_at: string;
  ends_at: string;
  capacity: number;
  selection_method: SelectionMethod;
  apply_starts_at: string;
  apply_ends_at: string;
  status: EventStatus;
  visibility: Visibility;
  header_image_url: string | null;
  application_state?: ApplicationState | null;
}

export interface EventUpsert {
  title: string;
  description: string;
  platform: EventPlatform;
  world_name: string | null;
  world_url: string | null;
  starts_at: string;
  ends_at: string;
  capacity: number;
  selection_method: SelectionMethod;
  apply_starts_at: string;
  apply_ends_at: string;
  visibility: Visibility;
  header_image_url: string | null;
}

export interface PageMeta {
  page: number;
  per_page: number;
  total: number;
}

export interface EventList {
  items: EventData[];
  meta: PageMeta;
}

export interface PublicOrganization {
  name: string;
  slug: string;
  description: string | null;
  website_url: string | null;
  events: EventData[];
}

// --- M3: フォーム・応募 ---

export type FormItemType =
  | "text"
  | "textarea"
  | "select"
  | "radio"
  | "checkbox"
  | "number";

export type AutofillKey =
  | "display_name"
  | "vrchat_username"
  | "platform"
  | "device_note"
  | "x_account"
  | "discord_account";

export interface FormItem {
  id: string;
  label: string;
  help_text: string | null;
  item_type: FormItemType;
  options: string[] | null;
  is_required: boolean;
  autofill_key: AutofillKey | null;
  sort_order: number;
}

export interface FormItemDraft {
  id?: string;
  label: string;
  help_text: string | null;
  item_type: FormItemType;
  options: string[] | null;
  is_required: boolean;
  autofill_key: AutofillKey | null;
}

export interface FormResponse {
  items: FormItem[];
  prefill: Record<string, string> | null;
}

export interface AnswerIn {
  form_item_id: string;
  value?: string;
  values?: string[];
}

export interface AnswerOut {
  form_item_id: string;
  label: string;
  item_type: string;
  value: string | null;
  values: string[] | null;
}

export type ApplicationStatus =
  | "pending"
  | "won"
  | "lost"
  | "waitlisted"
  | "canceled";

export interface Application {
  id: string;
  event_id: string;
  status: ApplicationStatus;
  promoted: boolean;
  applied_at: string;
  canceled_at: string | null;
  answers: AnswerOut[];
}

export interface ApplicantItem {
  id: string;
  status: ApplicationStatus;
  promoted: boolean;
  applied_at: string;
  display_name: string | null;
  vrchat_username: string | null;
  answers: AnswerOut[];
}

// --- M4: 抽選・通知 ---

export type QuotaFilter = "all" | "first_timer" | "repeater";

export interface Quota {
  name: string;
  label?: string | null;
  count: number | null;
  filter: QuotaFilter;
}

export interface LotteryRequest {
  quotas: Quota[];
  waitlist_count: number;
}

export interface LotteryPreview {
  target_count: number;
  remaining_capacity: number;
  quota_matches: Record<string, number>;
}

export interface LotteryExecuteResult {
  lottery_id: string;
  round: number;
  won: number;
  waitlisted: number;
  lost: number;
  executed_at: string;
}

export interface LotteryHistoryItem {
  id: string;
  round: number;
  executed_by_email: string;
  algorithm_version: string;
  winner_quota: number;
  waitlist_quota: number;
  config: { quotas: Quota[]; waitlist_count: number };
  executed_at: string;
}

export interface LotteryResultItem {
  application_id: string;
  display_name: string | null;
  result: "won" | "waitlisted" | "lost";
  draw_rank: number;
  quota_name: string;
  current_status: string;
}

export type NotificationChannel = "in_app" | "email" | "push";

export interface BroadcastRequest {
  type: "reminder" | "announcement";
  target: "won" | "all_applicants";
  title: string;
  body: string;
  channels: NotificationChannel[];
}

export interface NotificationItem {
  id: string;
  event_id: string | null;
  type: string;
  channel: string;
  title: string;
  body: string;
  status: string;
  read_at: string | null;
  created_at: string;
}

export interface NotificationHistory {
  summary: { type: string; channel: string; status: string; count: number }[];
  items: NotificationItem[];
}

// --- M6: 分析 ---

export interface EventAnalytics {
  applications_total: number;
  by_status: Record<string, number>;
  checkin_rate: number;
  first_timer_rate: number;
  daily_applications: { date: string; count: number }[];
}

export interface OrgAnalyticsSummary {
  events: {
    event_id: string;
    title: string;
    starts_at: string;
    status: string;
    applications_total: number;
    won_count: number;
    checkin_count: number;
    checkin_rate: number;
  }[];
  unique_attendees: number;
  repeat_attendees: number;
  repeat_rate: number;
}

// --- M5: 入場管理 ---

export interface CheckinItem {
  id: string;
  application_id: string;
  short_code: string;
  display_name: string | null;
  vrchat_username: string | null;
  method: "code" | "qr" | "manual";
  operator_email: string | null;
  checked_in_at: string;
}

export interface CheckinList {
  items: CheckinItem[];
  won_count: number;
  checkin_count: number;
  checkin_rate: number;
}

export interface MyApplication {
  id: string;
  status: ApplicationStatus;
  promoted: boolean;
  applied_at: string;
  event: {
    id: string;
    title: string;
    starts_at: string;
    ends_at: string;
    status: string;
    selection_method: string;
    organization_name: string;
  };
  short_code: string;
}
