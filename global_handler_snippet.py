@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=200, 
        content={"reply": f"⚠️ **System Error:** {str(exc)}"}
    )
