// Stub NDI library for link-time only.
// At runtime, the real libndi.so is loaded via LD_LIBRARY_PATH.
// All functions return 0/NULL — they are never actually called from this stub.
#include <stdint.h>
#include <stdbool.h>

typedef void* NDIlib_find_instance_t;
typedef void* NDIlib_recv_instance_t;
typedef void* NDIlib_send_instance_t;
typedef void* NDIlib_framesync_instance_t;
typedef void* NDIlib_source_t;
typedef void* NDIlib_video_frame_v2_t;
typedef void* NDIlib_audio_frame_v3_t;
typedef void* NDIlib_metadata_frame_t;
typedef void* NDIlib_tally_t;

bool    NDIlib_initialize(void)                            { return false; }
void    NDIlib_destroy(void)                               {}
const char* NDIlib_version(void)                           { return "stub"; }
bool    NDIlib_is_supported_CPU(void)                      { return false; }

void*   NDIlib_find_create_v2(const void* p)               { return 0; }
void    NDIlib_find_destroy(void* p)                       {}
bool    NDIlib_find_wait_for_sources(void* p, uint32_t ms) { return false; }
const void* NDIlib_find_get_current_sources(void* p, uint32_t* n) { return 0; }
const void* NDIlib_find_get_sources(void* p, uint32_t* n, uint32_t ms) { return 0; }

void*   NDIlib_recv_create_v3(const void* p)               { return 0; }
void    NDIlib_recv_destroy(void* p)                       {}
int     NDIlib_recv_capture_v3(void* p, void* v, void* a, void* m, uint32_t ms) { return 0; }
void    NDIlib_recv_free_video_v2(void* p, const void* f)  {}
void    NDIlib_recv_free_audio_v3(void* p, const void* f)  {}
void    NDIlib_recv_free_metadata(void* p, const void* f)  {}
void    NDIlib_recv_free_(void* p, const void* f)          {}
int     NDIlib_recv_get_no_connections(void* p)            { return 0; }
void    NDIlib_recv_get_performance(void* p, void* t, void* d) {}
void    NDIlib_recv_get_queue(void* p, void* q)            {}
bool    NDIlib_recv_ptz_is_supported(void* p)              { return false; }
bool    NDIlib_recv_ptz_zoom(void* p, float v)             { return false; }
bool    NDIlib_recv_ptz_zoom_speed(void* p, float v)       { return false; }
bool    NDIlib_recv_ptz_pan_tilt(void* p, float x, float y) { return false; }
bool    NDIlib_recv_ptz_pan_tilt_speed(void* p, float x, float y) { return false; }
bool    NDIlib_recv_ptz_focus(void* p, float v)            { return false; }
bool    NDIlib_recv_ptz_focus_speed(void* p, float v)      { return false; }
bool    NDIlib_recv_ptz_auto_focus(void* p)                { return false; }
bool    NDIlib_recv_ptz_exposure_auto(void* p)             { return false; }
bool    NDIlib_recv_ptz_exposure_manual(void* p, float v)  { return false; }
bool    NDIlib_recv_ptz_exposure_manual_v2(void* p, float v, float g, float s) { return false; }
bool    NDIlib_recv_ptz_white_balance_auto(void* p)        { return false; }
bool    NDIlib_recv_ptz_white_balance_indoor(void* p)      { return false; }
bool    NDIlib_recv_ptz_white_balance_outdoor(void* p)     { return false; }
bool    NDIlib_recv_ptz_white_balance_oneshot(void* p)     { return false; }
bool    NDIlib_recv_ptz_white_balance_manual(void* p, float r, float b) { return false; }
bool    NDIlib_recv_ptz_store_preset(void* p, int idx)     { return false; }
bool    NDIlib_recv_ptz_recall_preset(void* p, int idx, float s) { return false; }

void*   NDIlib_send_create(const void* p)                  { return 0; }
void    NDIlib_send_destroy(void* p)                       {}
void    NDIlib_send_send_video_v2(void* p, const void* f)  {}
void    NDIlib_send_send_video_async_v2(void* p, const void* f) {}
void    NDIlib_send_send_audio_v3(void* p, const void* f)  {}
void    NDIlib_send_send_metadata(void* p, const void* f)  {}
void    NDIlib_send_add_connection_metadata(void* p, const void* f) {}
void    NDIlib_send_clear_connection_metadata(void* p)     {}
int     NDIlib_send_get_no_connections(void* p, uint32_t ms) { return 0; }
bool    NDIlib_send_get_tally(void* p, void* t, uint32_t ms) { return false; }
const void* NDIlib_send_get_source_name(void* p)           { return 0; }
void    NDIlib_send_set_failover(void* p, const void* s)   {}
void    NDIlib_send_set_video_async_completion(void* p, void* fn, void* ctx) {}

void*   NDIlib_framesync_create(void* p)                   { return 0; }
void    NDIlib_framesync_destroy(void* p)                  {}
void    NDIlib_framesync_capture_video(void* p, void* f, int t) {}
void    NDIlib_framesync_free_video(void* p, void* f)      {}
void    NDIlib_framesync_capture_audio_v2(void* p, void* f, int sr, int ch, int ns) {}
void    NDIlib_framesync_free_audio_v2(void* p, void* f)   {}
int     NDIlib_framesync_audio_queue_depth(void* p)        { return 0; }
