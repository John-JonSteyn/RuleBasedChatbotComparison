mod cli;
mod config;
mod data_model;
mod io_decks;
mod logging_io;
mod normalise;
mod timing;
mod tokenise;
mod topics;
mod scoring {
    pub mod keyword;
    pub mod tfidf;
}

fn main() {
    if let Err(error) = cli::run() {
        eprintln!("Error: {error}");
        std::process::exit(1);
    }
}
