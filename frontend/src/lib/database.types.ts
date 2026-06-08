export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      analytics_weekly: {
        Row: {
          agent_calls: Json | null
          flushed_at: string | null
          grounding_calls: number | null
          new_users: number | null
          promo_redeemed: Json | null
          token_usage: Json | null
          total_cost_credits: number | null
          total_interactions: number | null
          week_ending: string
        }
        Insert: {
          agent_calls?: Json | null
          flushed_at?: string | null
          grounding_calls?: number | null
          new_users?: number | null
          promo_redeemed?: Json | null
          token_usage?: Json | null
          total_cost_credits?: number | null
          total_interactions?: number | null
          week_ending: string
        }
        Update: {
          agent_calls?: Json | null
          flushed_at?: string | null
          grounding_calls?: number | null
          new_users?: number | null
          promo_redeemed?: Json | null
          token_usage?: Json | null
          total_cost_credits?: number | null
          total_interactions?: number | null
          week_ending?: string
        }
        Relationships: []
      }
      chat_threads: {
        Row: {
          created_at: string
          id: string
          kind: string
          owner_user_id: string
          title: string | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          id?: string
          kind: string
          owner_user_id: string
          title?: string | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          id?: string
          kind?: string
          owner_user_id?: string
          title?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "chat_threads_owner_user_id_fkey"
            columns: ["owner_user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      conversations: {
        Row: {
          recent_messages: Json | null
          summary: string | null
          updated_at: string | null
          user_id: string
        }
        Insert: {
          recent_messages?: Json | null
          summary?: string | null
          updated_at?: string | null
          user_id: string
        }
        Update: {
          recent_messages?: Json | null
          summary?: string | null
          updated_at?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "conversations_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: true
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      credits: {
        Row: {
          balance: number
          initial_grant: number
          total_spent: number
          updated_at: string | null
          used_promos: string[] | null
          user_id: string
          welcome_credits_claimed_at: string | null
        }
        Insert: {
          balance?: number
          initial_grant?: number
          total_spent?: number
          updated_at?: string | null
          used_promos?: string[] | null
          user_id: string
          welcome_credits_claimed_at?: string | null
        }
        Update: {
          balance?: number
          initial_grant?: number
          total_spent?: number
          updated_at?: string | null
          used_promos?: string[] | null
          user_id?: string
          welcome_credits_claimed_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "credits_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: true
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      feedback: {
        Row: {
          category: string
          conversation_context: Json | null
          created_at: string | null
          id: number
          text: string
          user_id: string
        }
        Insert: {
          category: string
          conversation_context?: Json | null
          created_at?: string | null
          id?: never
          text: string
          user_id: string
        }
        Update: {
          category?: string
          conversation_context?: Json | null
          created_at?: string | null
          id?: never
          text?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "feedback_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      link_tokens: {
        Row: {
          created_at: string
          expires_at: string
          kind: string
          token: string
          user_id: string
        }
        Insert: {
          created_at?: string
          expires_at?: string
          kind?: string
          token?: string
          user_id: string
        }
        Update: {
          created_at?: string
          expires_at?: string
          kind?: string
          token?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "telegram_link_tokens_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      messages: {
        Row: {
          body: string
          body_tsv: unknown
          created_at: string
          id: number
          metadata: Json
          sender_type: string
          sender_user_id: string | null
          source: string
          thread_id: string
        }
        Insert: {
          body: string
          body_tsv?: unknown
          created_at?: string
          id?: never
          metadata?: Json
          sender_type: string
          sender_user_id?: string | null
          source: string
          thread_id: string
        }
        Update: {
          body?: string
          body_tsv?: unknown
          created_at?: string
          id?: never
          metadata?: Json
          sender_type?: string
          sender_user_id?: string | null
          source?: string
          thread_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "messages_sender_user_id_fkey"
            columns: ["sender_user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "messages_thread_id_fkey"
            columns: ["thread_id"]
            isOneToOne: false
            referencedRelation: "chat_threads"
            referencedColumns: ["id"]
          },
        ]
      }
      off_topic_state: {
        Row: {
          count: number | null
          last_flagged_ts: string | null
          restricted_until: string | null
          user_id: string
        }
        Insert: {
          count?: number | null
          last_flagged_ts?: string | null
          restricted_until?: string | null
          user_id: string
        }
        Update: {
          count?: number | null
          last_flagged_ts?: string | null
          restricted_until?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "off_topic_state_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: true
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      trip_bookings: {
        Row: {
          confirmation_code: string | null
          created_at: string
          datetime_local: string | null
          id: string
          kind: string
          payload: Json
          trip_id: string
          updated_at: string
        }
        Insert: {
          confirmation_code?: string | null
          created_at?: string
          datetime_local?: string | null
          id?: string
          kind: string
          payload?: Json
          trip_id: string
          updated_at?: string
        }
        Update: {
          confirmation_code?: string | null
          created_at?: string
          datetime_local?: string | null
          id?: string
          kind?: string
          payload?: Json
          trip_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "trip_bookings_trip_id_fkey"
            columns: ["trip_id"]
            isOneToOne: false
            referencedRelation: "trips"
            referencedColumns: ["id"]
          },
        ]
      }
      trip_checklist: {
        Row: {
          created_at: string
          done: boolean
          id: string
          label: string
          ord: number
          scope: string
          trip_id: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          done?: boolean
          id?: string
          label: string
          ord?: number
          scope: string
          trip_id: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          done?: boolean
          id?: string
          label?: string
          ord?: number
          scope?: string
          trip_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "trip_checklist_trip_id_fkey"
            columns: ["trip_id"]
            isOneToOne: false
            referencedRelation: "trips"
            referencedColumns: ["id"]
          },
        ]
      }
      trip_day_blocks: {
        Row: {
          created_at: string
          day_id: string
          duration_min: number | null
          energy: number | null
          id: string
          lat: number | null
          lng: number | null
          ord: number
          time_slot: string | null
          title: string
          trip_id: string
          type: string | null
          updated_at: string
          walk: string | null
          why: string | null
        }
        Insert: {
          created_at?: string
          day_id: string
          duration_min?: number | null
          energy?: number | null
          id?: string
          lat?: number | null
          lng?: number | null
          ord?: number
          time_slot?: string | null
          title: string
          trip_id: string
          type?: string | null
          updated_at?: string
          walk?: string | null
          why?: string | null
        }
        Update: {
          created_at?: string
          day_id?: string
          duration_min?: number | null
          energy?: number | null
          id?: string
          lat?: number | null
          lng?: number | null
          ord?: number
          time_slot?: string | null
          title?: string
          trip_id?: string
          type?: string | null
          updated_at?: string
          walk?: string | null
          why?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "trip_day_blocks_day_id_fkey"
            columns: ["day_id"]
            isOneToOne: false
            referencedRelation: "trip_days"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "trip_day_blocks_trip_id_fkey"
            columns: ["trip_id"]
            isOneToOne: false
            referencedRelation: "trips"
            referencedColumns: ["id"]
          },
        ]
      }
      trip_days: {
        Row: {
          ai_note: string | null
          created_at: string
          date: string | null
          energy_target: number | null
          id: string
          n: number
          title: string | null
          trip_id: string
          updated_at: string
          weather_snapshot: string | null
        }
        Insert: {
          ai_note?: string | null
          created_at?: string
          date?: string | null
          energy_target?: number | null
          id?: string
          n: number
          title?: string | null
          trip_id: string
          updated_at?: string
          weather_snapshot?: string | null
        }
        Update: {
          ai_note?: string | null
          created_at?: string
          date?: string | null
          energy_target?: number | null
          id?: string
          n?: number
          title?: string | null
          trip_id?: string
          updated_at?: string
          weather_snapshot?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "trip_days_trip_id_fkey"
            columns: ["trip_id"]
            isOneToOne: false
            referencedRelation: "trips"
            referencedColumns: ["id"]
          },
        ]
      }
      trip_destinations: {
        Row: {
          created_at: string
          id: string
          iso_country: string | null
          name: string
          ord: number
          status: string
          trip_id: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          id?: string
          iso_country?: string | null
          name: string
          ord?: number
          status?: string
          trip_id: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          id?: string
          iso_country?: string | null
          name?: string
          ord?: number
          status?: string
          trip_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "trip_destinations_trip_id_fkey"
            columns: ["trip_id"]
            isOneToOne: false
            referencedRelation: "trips"
            referencedColumns: ["id"]
          },
        ]
      }
      trips: {
        Row: {
          budget: Json
          country_intel: Json
          cover: Json
          created_at: string
          discovery: Json
          id: string
          journal: Json
          live_state: Json
          preferences: Json
          reference_date: string | null
          saga_state: string | null
          scratchpad: Json
          status: string
          title: string | null
          travelers: Json
          updated_at: string
          user_id: string
          vision_summary: string | null
        }
        Insert: {
          budget?: Json
          country_intel?: Json
          cover?: Json
          created_at?: string
          discovery?: Json
          id?: string
          journal?: Json
          live_state?: Json
          preferences?: Json
          reference_date?: string | null
          saga_state?: string | null
          scratchpad?: Json
          status?: string
          title?: string | null
          travelers?: Json
          updated_at?: string
          user_id: string
          vision_summary?: string | null
        }
        Update: {
          budget?: Json
          country_intel?: Json
          cover?: Json
          created_at?: string
          discovery?: Json
          id?: string
          journal?: Json
          live_state?: Json
          preferences?: Json
          reference_date?: string | null
          saga_state?: string | null
          scratchpad?: Json
          status?: string
          title?: string | null
          travelers?: Json
          updated_at?: string
          user_id?: string
          vision_summary?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "trips_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      usage_tracking: {
        Row: {
          call_count: number | null
          grounded_prompt_count: number | null
          id: number
          model_name: string
          total_cost_credits: number | null
          total_input_tokens: number | null
          total_output_tokens: number | null
          updated_at: string | null
          user_id: string | null
        }
        Insert: {
          call_count?: number | null
          grounded_prompt_count?: number | null
          id?: never
          model_name: string
          total_cost_credits?: number | null
          total_input_tokens?: number | null
          total_output_tokens?: number | null
          updated_at?: string | null
          user_id?: string | null
        }
        Update: {
          call_count?: number | null
          grounded_prompt_count?: number | null
          id?: never
          model_name?: string
          total_cost_credits?: number | null
          total_input_tokens?: number | null
          total_output_tokens?: number | null
          updated_at?: string | null
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "usage_tracking_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      user_profiles: {
        Row: {
          form_response: Json | null
          profile_data: Json | null
          summary: string | null
          updated_at: string | null
          user_id: string
        }
        Insert: {
          form_response?: Json | null
          profile_data?: Json | null
          summary?: string | null
          updated_at?: string | null
          user_id: string
        }
        Update: {
          form_response?: Json | null
          profile_data?: Json | null
          summary?: string | null
          updated_at?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_profiles_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: true
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      users: {
        Row: {
          created_at: string | null
          id: string
          location: string | null
          name: string | null
          source: string | null
          submission_id: string | null
          telegram_id: string | null
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          id?: string
          location?: string | null
          name?: string | null
          source?: string | null
          submission_id?: string | null
          telegram_id?: string | null
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          id?: string
          location?: string | null
          name?: string | null
          source?: string | null
          submission_id?: string | null
          telegram_id?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      waitlist: {
        Row: {
          app_step: string
          created_at: string
          email: string
          id: string
          referrer: string | null
          status: string
          updated_at: string
          user_agent: string | null
        }
        Insert: {
          app_step?: string
          created_at?: string
          email: string
          id?: string
          referrer?: string | null
          status?: string
          updated_at?: string
          user_agent?: string | null
        }
        Update: {
          app_step?: string
          created_at?: string
          email?: string
          id?: string
          referrer?: string | null
          status?: string
          updated_at?: string
          user_agent?: string | null
        }
        Relationships: []
      }
    }
    Views: {
      vw_trips_growth: {
        Row: {
          status: string | null
          trips_created: number | null
          week: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      accumulate_user_usage: {
        Args: {
          p_cost_credits: number
          p_input_tokens: number
          p_is_grounded: number
          p_model_name: string
          p_output_tokens: number
          p_user_id: string
        }
        Returns: undefined
      }
      deduct_credits: {
        Args: { p_amount: number; p_user_id: string }
        Returns: number
      }
      derive_saga_state: { Args: { p_trip_id: string }; Returns: string }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
