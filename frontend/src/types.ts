export interface Sneaker {
    id: number;
    shoe_name: string;
    audience_score: number;
    best_price: number;
    style: string;
    shock_absorption: string;
    energy_return: string;
    traction: string;
    breathability: string;
    material: string;
    season: string;
    width_fit: string;
    top_style: string;
}


export interface Message {
    text: string;
    sender: 'user' | 'bot';
}
