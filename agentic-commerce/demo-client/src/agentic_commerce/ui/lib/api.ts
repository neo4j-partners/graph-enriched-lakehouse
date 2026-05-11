import { useQuery, useSuspenseQuery, useMutation } from "@tanstack/react-query";
import type { UseQueryOptions, UseSuspenseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
export class ApiError extends Error {
    status: number;
    statusText: string;
    body: unknown;
    constructor(status: number, statusText: string, body: unknown){
        super(`HTTP ${status}: ${statusText}`);
        this.name = "ApiError";
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}
export interface AgenticSearchIn {
    demo_mode?: "agentic_search" | null;
    demo_preset_id?: string | null;
    prompt: string;
    session_id?: string | null;
    user_id?: string | null;
}
export interface AgenticSearchOut {
    answer: string;
    databricks_request_id?: string | null;
    graph_hops?: GraphHop[];
    knowledge_chunks?: KnowledgeChunk[];
    memory_writes?: MemoryWrite[];
    mode?: "agentic_search" | "issue_diagnosis";
    product_picks?: ProductCard[];
    profile_chips?: ProfileChip[];
    raw_endpoint_metadata?: Record<string, unknown> | null;
    related_products?: ProductCard[];
    request_id: string;
    session_id: string;
    source_type: "live" | "sample" | "fallback";
    summary?: string | null;
    timing?: TimingMetadata;
    tool_timeline?: ToolTimelineItem[];
    trace_source?: "live" | "sample" | "inferred" | "unavailable";
    warnings?: DemoWarning[];
}
export interface CitedSource {
    id?: string | null;
    score?: number | null;
    snippet?: string | null;
    source_type?: string | null;
    title?: string | null;
}
export interface ComplexValue {
    display?: string | null;
    primary?: boolean | null;
    ref?: string | null;
    type?: string | null;
    value?: string | null;
}
export interface DemoError {
    code: string;
    fallback_available?: boolean;
    retryable?: boolean;
    technical_detail?: string | null;
    user_message: string;
}
export interface DemoWarning {
    code: string;
    message: string;
}
export interface DiagnosisPathStep {
    detail?: string | null;
    label: string;
}
export interface GraphHop {
    relationship: string;
    score?: number | null;
    source: string;
    target: string;
}
export interface HTTPValidationError {
    detail?: ValidationError[];
}
export interface IssueDiagnosisIn {
    demo_mode?: "issue_diagnosis" | null;
    demo_preset_id?: string | null;
    prompt: string;
    session_id?: string | null;
    user_id?: string | null;
}
export interface IssueDiagnosisOut {
    answer: string;
    cited_sources?: CitedSource[];
    compatible_alternatives?: ProductCard[];
    confidence?: number | null;
    databricks_request_id?: string | null;
    knowledge_chunks?: KnowledgeChunk[];
    mode?: "agentic_search" | "issue_diagnosis";
    path?: DiagnosisPathStep[];
    raw_endpoint_metadata?: Record<string, unknown> | null;
    recommended_actions?: RecommendedAction[];
    request_id: string;
    session_id: string;
    source_type: "live" | "sample" | "fallback";
    summary?: string | null;
    timing?: TimingMetadata;
    tool_timeline?: ToolTimelineItem[];
    trace_source?: "live" | "sample" | "inferred" | "unavailable";
    warnings?: DemoWarning[];
}
export interface KnowledgeChunk {
    features?: string[];
    id?: string | null;
    related_products?: string[];
    score?: number | null;
    solutions?: string[];
    source_type?: string | null;
    symptoms?: string[];
    text: string;
    title?: string | null;
}
export interface MemoryWrite {
    kind?: string | null;
    label: string;
    stored?: boolean | null;
    value: string;
}
export interface Name {
    family_name?: string | null;
    given_name?: string | null;
}
export interface ProductCard {
    brand?: string | null;
    category?: string | null;
    description?: string | null;
    id?: string | null;
    image_url?: string | null;
    in_stock?: boolean | null;
    name: string;
    price?: number | null;
    rationale?: string | null;
    score?: number | null;
    signals?: string[];
}
export interface ProfileChip {
    kind?: string | null;
    label: string;
    value: string;
}
export interface RecommendedAction {
    description?: string | null;
    label: string;
    priority?: string | null;
}
export interface TimingMetadata {
    total_ms?: number | null;
    upstream_ms?: number | null;
}
export interface ToolTimelineItem {
    duration_ms?: number | null;
    label?: string | null;
    status?: string;
    summary?: string | null;
    tool_name: string;
}
export interface User {
    active?: boolean | null;
    display_name?: string | null;
    emails?: ComplexValue[] | null;
    entitlements?: ComplexValue[] | null;
    external_id?: string | null;
    groups?: ComplexValue[] | null;
    id?: string | null;
    name?: Name | null;
    roles?: ComplexValue[] | null;
    schemas?: UserSchema[] | null;
    user_name?: string | null;
}
export const UserSchema = {
    "urn:ietf:params:scim:schemas:core:2.0:User": "urn:ietf:params:scim:schemas:core:2.0:User",
    "urn:ietf:params:scim:schemas:extension:workspace:2.0:User": "urn:ietf:params:scim:schemas:extension:workspace:2.0:User"
} as const;
export type UserSchema = typeof UserSchema[keyof typeof UserSchema];
export interface ValidationError {
    ctx?: Record<string, unknown>;
    input?: unknown;
    loc: (string | number)[];
    msg: string;
    type: string;
}
export interface VersionOut {
    version: string;
}
export interface CurrentUserParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const currentUser = async (params?: CurrentUserParams, options?: RequestInit): Promise<{
    data: User;
}> =>{
    const res = await fetch("/api/current-user", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const currentUserKey = (params?: CurrentUserParams)=>{
    return [
        "/api/current-user",
        params
    ] as const;
};
export function useCurrentUser<TData = {
    data: User;
}>(options?: {
    params?: CurrentUserParams;
    query?: Omit<UseQueryOptions<{
        data: User;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: currentUserKey(options?.params),
        queryFn: ()=>currentUser(options?.params),
        ...options?.query
    });
}
export function useCurrentUserSuspense<TData = {
    data: User;
}>(options?: {
    params?: CurrentUserParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: User;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: currentUserKey(options?.params),
        queryFn: ()=>currentUser(options?.params),
        ...options?.query
    });
}
export const runIssueDiagnosis = async (data: IssueDiagnosisIn, options?: RequestInit): Promise<{
    data: IssueDiagnosisOut;
}> =>{
    const res = await fetch("/api/demo/diagnose", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useRunIssueDiagnosis(options?: {
    mutation?: UseMutationOptions<{
        data: IssueDiagnosisOut;
    }, ApiError, IssueDiagnosisIn>;
}) {
    return useMutation({
        mutationFn: (data)=>runIssueDiagnosis(data),
        ...options?.mutation
    });
}
export const runAgenticSearch = async (data: AgenticSearchIn, options?: RequestInit): Promise<{
    data: AgenticSearchOut;
}> =>{
    const res = await fetch("/api/demo/search", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useRunAgenticSearch(options?: {
    mutation?: UseMutationOptions<{
        data: AgenticSearchOut;
    }, ApiError, AgenticSearchIn>;
}) {
    return useMutation({
        mutationFn: (data)=>runAgenticSearch(data),
        ...options?.mutation
    });
}
export const version = async (options?: RequestInit): Promise<{
    data: VersionOut;
}> =>{
    const res = await fetch("/api/version", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const versionKey = ()=>{
    return [
        "/api/version"
    ] as const;
};
export function useVersion<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}
export function useVersionSuspense<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}
