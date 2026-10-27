"""Streamlit web interface for the research-brief agent."""
import streamlit as st

from agent import research_brief

st.set_page_config(page_title="Research Brief Agent", page_icon="🔎")

st.title("🔎 Research Brief Agent")
st.caption("Enter a topic. The agent searches the web, then summarizes "
           "the findings into three bullet points.")

topic = st.text_input("Topic", placeholder="e.g. Latest developments in quantum computing")

if st.button("Generate brief", type="primary"):
    if not topic.strip():
        st.warning("Please enter a topic first.")
    else:
        status = st.empty()
        try:
            result = research_brief(topic, progress=lambda msg: status.info(msg))
            status.empty()
            st.subheader(f"Research brief: {result['topic']}")
            for bullet in result["bullets"]:
                st.markdown(f"- {bullet}")
            st.caption(f"Search {result['search_seconds']:.1f}s · "
                       f"Summary {result['summary_seconds']:.1f}s · "
                       f"Total {result['total_seconds']:.1f}s · Model: {result['model']}")
            with st.expander("Show raw search results"):
                st.text(result["raw"])
        except ValueError as err:
            status.empty()
            st.warning(str(err))
        except Exception as err:                # details are already in the logs
            status.empty()
            st.error(f"Something went wrong: {err}")
