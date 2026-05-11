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
export interface AnswerTable {
    headers: string[];
    rows: string[][];
}
export interface AskIn {
    conversation_id?: string | null;
    question: string;
}
export interface AskOut {
    conversation_id: string;
    message_id: string;
    summary?: string | null;
    table?: AnswerTable | null;
    text: string;
}
export interface ComplexValue {
    display?: string | null;
    primary?: boolean | null;
    ref?: string | null;
    type?: string | null;
    value?: string | null;
}
export interface Graph {
    edges: GraphEdge[];
    nodes: GraphNode[];
}
export interface GraphEdge {
    source: string;
    target: string;
}
export interface GraphNode {
    id: string;
    is_hub: boolean;
    risk: "H" | "M" | "L";
}
export interface HTTPValidationError {
    detail?: ValidationError[];
}
export interface HubAccountOut {
    account_id: string;
    betweenness: number;
    neighbors: number;
    shortest_paths: number;
}
export interface LoadIn {
    central_account_ids?: string[];
    ring_ids?: string[];
    risk_account_ids?: string[];
}
export interface LoadOut {
    quality_checks: QualityCheck[];
    row_counts: Record<string, number>;
    steps: LoadStep[];
    target_tables: string[];
}
export interface LoadStep {
    detail?: string | null;
    label: string;
    status: "done" | "now" | "todo";
}
export interface Name {
    family_name?: string | null;
    given_name?: string | null;
}
export interface QualityCheck {
    name: string;
    passed: boolean;
}
export interface RingOut {
    graph: Graph;
    nodes: number;
    ring_id: string;
    risk: "H" | "M" | "L";
    risk_score: number;
    shared_identifiers: string[];
    topology: "star" | "mesh" | "chain";
    volume: number;
}
export interface RiskAccountOut {
    account_age_days: number;
    account_id: string;
    merchant_diversity: "Low" | "Medium" | "High";
    risk_score: number;
    velocity: "Low" | "Medium" | "High";
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
export const askGenie = async (data: AskIn, options?: RequestInit): Promise<{
    data: AskOut;
}> =>{
    const res = await fetch("/api/genie/ask", {
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
export function useAskGenie(options?: {
    mutation?: UseMutationOptions<{
        data: AskOut;
    }, ApiError, AskIn>;
}) {
    return useMutation({
        mutationFn: (data)=>askGenie(data),
        ...options?.mutation
    });
}
export const loadRings = async (data: LoadIn, options?: RequestInit): Promise<{
    data: LoadOut;
}> =>{
    const res = await fetch("/api/load", {
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
export function useLoadRings(options?: {
    mutation?: UseMutationOptions<{
        data: LoadOut;
    }, ApiError, LoadIn>;
}) {
    return useMutation({
        mutationFn: (data)=>loadRings(data),
        ...options?.mutation
    });
}
export const searchCentralAccounts = async (options?: RequestInit): Promise<{
    data: HubAccountOut[];
}> =>{
    const res = await fetch("/api/search/hubs", {
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
export const searchCentralAccountsKey = ()=>{
    return [
        "/api/search/hubs"
    ] as const;
};
export function useSearchCentralAccounts<TData = {
    data: HubAccountOut[];
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: HubAccountOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: searchCentralAccountsKey(),
        queryFn: ()=>searchCentralAccounts(),
        ...options?.query
    });
}
export function useSearchCentralAccountsSuspense<TData = {
    data: HubAccountOut[];
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: HubAccountOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: searchCentralAccountsKey(),
        queryFn: ()=>searchCentralAccounts(),
        ...options?.query
    });
}
export interface SearchRingsParams {
    max_nodes?: number;
}
export const searchRings = async (params?: SearchRingsParams, options?: RequestInit): Promise<{
    data: RingOut[];
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.max_nodes != null) searchParams.set("max_nodes", String(params?.max_nodes));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/search/rings?${queryString}` : "/api/search/rings";
    const res = await fetch(url, {
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
export const searchRingsKey = (params?: SearchRingsParams)=>{
    return [
        "/api/search/rings",
        params
    ] as const;
};
export function useSearchRings<TData = {
    data: RingOut[];
}>(options?: {
    params?: SearchRingsParams;
    query?: Omit<UseQueryOptions<{
        data: RingOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: searchRingsKey(options?.params),
        queryFn: ()=>searchRings(options?.params),
        ...options?.query
    });
}
export function useSearchRingsSuspense<TData = {
    data: RingOut[];
}>(options?: {
    params?: SearchRingsParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: RingOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: searchRingsKey(options?.params),
        queryFn: ()=>searchRings(options?.params),
        ...options?.query
    });
}
export const searchRiskAccounts = async (options?: RequestInit): Promise<{
    data: RiskAccountOut[];
}> =>{
    const res = await fetch("/api/search/risk", {
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
export const searchRiskAccountsKey = ()=>{
    return [
        "/api/search/risk"
    ] as const;
};
export function useSearchRiskAccounts<TData = {
    data: RiskAccountOut[];
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: RiskAccountOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: searchRiskAccountsKey(),
        queryFn: ()=>searchRiskAccounts(),
        ...options?.query
    });
}
export function useSearchRiskAccountsSuspense<TData = {
    data: RiskAccountOut[];
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: RiskAccountOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: searchRiskAccountsKey(),
        queryFn: ()=>searchRiskAccounts(),
        ...options?.query
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
